"""
Refresh Token Provider: issue, rotate, revoke, verify
"""
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from uuid import UUID

from portal.config import settings
from portal.exceptions.responses import RefreshTokenInvalidException
from portal.libs.contexts.request_context import get_request_context, RequestContext
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import PortalRefreshToken, PortalAuthDevice
from portal.schemas.base import RefreshTokenData


class RefreshTokenProvider:
    """Manage opaque refresh tokens with rotation and reuse detection"""

    def __init__(self, session: Session):
        self._session = session
        self._salt = settings.REFRESH_TOKEN_HASH_SALT
        self._pepper = settings.REFRESH_TOKEN_HASH_PEPPER
        self._ttl_days = settings.REFRESH_TOKEN_EXPIRE_DAYS
        self._req_ctx: RequestContext = get_request_context()
        self._secrets_length = 96

    def _hash_token(self, token: str) -> str:
        return hashlib.sha512(f"{self._salt}{token}{self._pepper}".encode()).hexdigest()

    def _generate_token(self) -> str:
        return secrets.token_urlsafe(self._secrets_length)

    async def issue(
        self,
        user_id: UUID,
        device_id: UUID,
        family_id: UUID
    ) -> str:
        """

        :param user_id:
        :param device_id:
        :param family_id:
        :return:
        """
        refresh_token = self._generate_token()
        token_hash = self._hash_token(token=refresh_token)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=self._ttl_days)
        user_agent = self._req_ctx.user_agent or None
        ip = self._req_ctx.ip or self._req_ctx.client_ip or None
        try:
            # Upsert PortalAuthDevice
            await (
                self._session.insert(PortalAuthDevice)
                .values(
                    id=device_id,
                    user_id=user_id,
                    last_ip=ip,
                    last_user_agent=user_agent
                )
                .on_conflict_do_update(
                    constraint="pk_portal_auth_device",
                    set_={
                        "last_seen_at": now,
                        "last_ip": ip,
                        "last_user_agent": user_agent,
                    }
                )
                .execute()
            )
            rt_data: RefreshTokenData = RefreshTokenData(
                user_id=user_id,
                device_id=device_id,
                family_id=family_id,
                token_hash=token_hash,
                expires_at=expires_at,
                last_used_at=now,
                ip=ip,
                user_agent=user_agent,
            )
            await (
                self._session.insert(PortalRefreshToken)
                .values(rt_data.model_dump(exclude_none=True))
                .execute()
            )
        except Exception as e:
            raise e
        else:
            return refresh_token

    async def rotate(self, refresh_token: str) -> tuple[str, RefreshTokenData]:
        """Rotate refresh token; detect reuse and revoke family on reuse."""
        now = datetime.now(timezone.utc)
        token_hash = self._hash_token(token=refresh_token)
        rt_data: RefreshTokenData = await self._session.select(PortalRefreshToken).where(
            PortalRefreshToken.token_hash == token_hash
        ).fetchrow(as_model=RefreshTokenData)
        if not rt_data:
            raise RefreshTokenInvalidException()

        if rt_data.revoked_at is not None or now > rt_data.expires_at:
            raise RefreshTokenInvalidException()

        # Reuse detection: if already replaced, entire family is compromised
        if rt_data.replaced_by_id is not None:
            await self.revoke_family(rt_data.family_id, reason="Refresh token reused")
            raise RefreshTokenInvalidException("Refresh token reused.")

        try:
            user_agent = self._req_ctx.user_agent or None
            # Create new token within same family
            new_refresh_token = self._generate_token()
            new_hash = self._hash_token(token=new_refresh_token)

            new_rt_data: RefreshTokenData = RefreshTokenData(
                user_id=rt_data.user_id,
                device_id=rt_data.device_id,
                family_id=rt_data.family_id,
                parent_id=rt_data.id,
                replaced_by_id=None,
                token_hash=new_hash,
                expires_at=rt_data.expires_at,
                last_used_at=now,
                revoked_at=None,
                revoked_reason=None,
                ip=self._req_ctx.ip or self._req_ctx.client_ip or None,
                user_agent=user_agent
            )
            # Update device last seen
            if rt_data.device_id:
                await (
                    self._session.update(PortalAuthDevice)
                    .where(PortalAuthDevice.id == rt_data.device_id)
                    .values(last_seen_at=now, last_ip=self._req_ctx.ip or self._req_ctx.client_ip or None, last_user_agent=user_agent)
                    .execute()
                )
            await self._session.insert(PortalRefreshToken).values(new_rt_data.model_dump(exclude_none=True)).execute()

            # mark old as replaced
            await (
                self._session.update(PortalRefreshToken)
                .where(PortalRefreshToken.id == rt_data.id)
                .values(replaced_by_id=new_rt_data.id, last_used_at=now)
                .execute()
            )
        except Exception as e:
            logger.exception(e)
            raise e
        else:
            return new_refresh_token, new_rt_data

    async def revoke_family(self, family_id: UUID, reason: str = "Manual Revoke") -> None:
        now = datetime.now(timezone.utc)
        try:
            await (
                self._session.update(PortalRefreshToken)
                .where(PortalRefreshToken.family_id == family_id)
                .values(revoked_at=now, revoked_reason=reason)
                .execute()
            )
        except Exception as e:
            raise e
        else:
            await self._session.commit()

    async def revoke_by_token(self, token: str, revoke_family: bool = True) -> bool:
        """
        Revoke by refresh token string (optionally entire family).
        :param token: Hashed token
        :param revoke_family:
        :return:
        """
        token_hash = self._hash_token(token=token)
        rt_data: RefreshTokenData = await (
            self._session.select(PortalRefreshToken)
            .where(PortalRefreshToken.token_hash == token_hash)
            .fetchrow(as_model=RefreshTokenData)
        )
        if not rt_data:
            return False
        if revoke_family:
            await self.revoke_family(rt_data.family_id, reason="Logout")
            return True
        try:
            now = datetime.now(timezone.utc)
            await (
                self._session.update(PortalRefreshToken)
                .where(PortalRefreshToken.id == rt_data.id)
                .values(revoked_at=now, revoked_reason="Logout")
                .execute()
            )
        except Exception as e:
            raise e
        else:
            return True
