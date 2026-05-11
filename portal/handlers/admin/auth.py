"""
Admin authentication: password login, Microsoft Entra ID exchange, refresh, logout.
"""
import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

import jwt
from fastapi import status

from portal.config import settings
from portal.exceptions.responses import RefreshTokenInvalidException, UnauthorizedException, ApiBaseException
from portal.handlers.admin.user import AdminUserHandler
from portal.libs.consts.enums import AccessTokenAudType, ThirdPartyProvider
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import AuthUser, AuthUserThirdParty
from portal.providers.jwt_provider import JWTProvider
from portal.providers.microsoft_oidc_provider import MicrosoftOidcProvider
from portal.providers.password_provider import PasswordProvider
from portal.providers.refresh_token_provider import RefreshTokenProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider
from portal.schemas.base import AccessTokenPayload
from portal.schemas.user import SUserSensitive
from portal.serializers.admin.v1.auth import (
    AdminLoginResponse,
    AdminInfo,
)
from portal.serializers.mixins import TokenResponse
from .permission import AdminPermissionHandler
from .role import AdminRoleHandler


class AdminAuthHandler:
    """Issue portal admin JWT after password or Microsoft ID token verification."""

    def __init__(
        self,
        session: Session,
        jwt_provider: JWTProvider,
        refresh_token_provider: RefreshTokenProvider,
        token_blacklist_provider: TokenBlacklistProvider,
        admin_user_handler: AdminUserHandler,
        admin_permission_handler: AdminPermissionHandler,
        admin_role_handler: AdminRoleHandler,
        password_provider: PasswordProvider,
        microsoft_oidc_provider: MicrosoftOidcProvider,
    ):
        self._expires_in = 60 * 60 * 24  # 24 hours
        self._session = session
        self._jwt_provider = jwt_provider
        self._refresh_token_provider = refresh_token_provider
        self._token_blacklist_provider = token_blacklist_provider
        self._admin_user_handler = admin_user_handler
        self._admin_permission_handler = admin_permission_handler
        self._admin_role_handler = admin_role_handler
        self._password_provider = password_provider
        self._microsoft_oidc_provider = microsoft_oidc_provider

    def _roles_for_jwt(self, user: SUserSensitive, role_codes: list[str]) -> list[str]:
        roles = list(role_codes)
        if user.is_superuser and "superadmin" not in roles:
            roles.append("superadmin")
        return roles

    async def _upsert_auth_user_third_party(
        self,
        user_id: UUID,
        provider: ThirdPartyProvider,
        provider_uid: str,
        provider_tenant_id: UUID,
        additional_data: dict[str, Any],
        token_expires_at: Optional[datetime] = None,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        row_id = uuid4()
        serialized_additional_data = json.dumps(additional_data)
        await (
            self._session.insert(AuthUserThirdParty)
            .values(
                id=row_id,
                user_id=user_id,
                provider=provider.value,
                provider_tenant_id=provider_tenant_id,
                provider_uid=provider_uid,
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                additional_data=serialized_additional_data,
                is_deleted=False,
                created_by="oauth",
                updated_by="oauth",
            )
            .on_conflict_do_update(
                index_elements=["user_id", "provider", "provider_uid"],
                set_={
                    "provider_tenant_id": provider_tenant_id,
                    "token_expires_at": token_expires_at,
                    "additional_data": serialized_additional_data,
                    "updated_at": now,
                    "updated_by": "oauth",
                    "is_deleted": False,
                },
            )
            .execute()
        )

    async def _record_microsoft_third_party_login(self, user_id: UUID, claims: dict[str, Any]) -> None:
        oid_raw = claims.get("oid") or claims.get("sub")
        tid_raw = claims.get("tid")
        if not oid_raw or not tid_raw:
            logger.warning("Microsoft ID token missing oid/sub or tid; skip AuthUserThirdParty upsert")
            return
        provider_uid = str(oid_raw).strip()
        if not provider_uid:
            return
        try:
            tenant_uuid = UUID(str(tid_raw).strip())
        except ValueError:
            logger.warning("Microsoft token tid is not a valid UUID: %s", tid_raw)
            return
        exp_raw = claims.get("exp")
        token_expires_at: Optional[datetime] = None
        if isinstance(exp_raw, (int, float)):
            token_expires_at = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)
        elif isinstance(exp_raw, str) and exp_raw.isdigit():
            token_expires_at = datetime.fromtimestamp(int(exp_raw), tz=timezone.utc)
        additional_data: dict[str, Any] = {
            "email": claims.get("email") or claims.get("preferred_username"),
            "name": claims.get("name"),
            "auth_time": claims.get("auth_time"),
        }
        try:
            await self._upsert_auth_user_third_party(
                user_id=user_id,
                provider=ThirdPartyProvider.MICROSOFT,
                provider_uid=provider_uid,
                provider_tenant_id=tenant_uuid,
                additional_data=additional_data,
                token_expires_at=token_expires_at,
            )
        except Exception:
            logger.exception("Failed to upsert AuthUserThirdParty for Microsoft login")

    async def _complete_admin_login(self, user: SUserSensitive) -> AdminLoginResponse:
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")

        roles = await self._admin_role_handler.init_user_roles_cache(user, self._expires_in)
        permissions = await self._admin_permission_handler.init_user_permissions_cache(user, self._expires_in)

        family_id = uuid4()
        device_id = uuid4()
        access_token = self._jwt_provider.create_access_token(
            user=user,
            family_id=family_id,
            roles=roles,
            permissions=permissions,
            aud_type=AccessTokenAudType.ADMIN,
        )
        refresh_token = await self._refresh_token_provider.issue(
            user_id=user.id,
            device_id=device_id,
            family_id=family_id,
        )

        now = datetime.now(timezone.utc)
        await (
            self._session.update(AuthUser)
            .where(AuthUser.id == user.id)
            .values(last_login_at=now)
            .execute()
        )

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )
        admin = AdminInfo(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            roles=roles,
            preferred_locale_id=user.preferred_locale_id,
            last_login_at=user.last_login_at,
        )
        return AdminLoginResponse(admin=admin, token=token)

    async def login_with_password(self, email: str, password: str) -> AdminLoginResponse:
        """
        Login with email and password. (Local only)
        :param email:
        :param password:
        :return:
        """
        user = await self._admin_user_handler.get_user_detail_by_email(email)
        if not user or not user.password_hash:
            raise UnauthorizedException(detail="Invalid email or password")
        if not self._password_provider.verify_password(password, user.password_hash):
            raise UnauthorizedException(detail="Invalid email or password")
        return await self._complete_admin_login(user)

    async def microsoft_login(self, id_token: str) -> AdminLoginResponse:
        """
        Microsoft Entra ID login.
        :param id_token:
        :return:
        """
        if not self._microsoft_oidc_provider.is_configured():
            raise ApiBaseException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Microsoft OIDC is not configured")
        try:
            claims: dict[str, Any] = self._microsoft_oidc_provider.verify_id_token(id_token)
        except jwt.PyJWTError:
            raise UnauthorizedException(detail="Invalid Microsoft token")

        email_raw = claims.get("upn")
        if not email_raw:
            raise UnauthorizedException(detail="Invalid Microsoft token: missing upn claim")
        email = str(email_raw).strip().lower()

        user = await self._admin_user_handler.get_user_detail_by_email(email)
        if not user:
            raise UnauthorizedException(detail="User not found")
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")
        await self._record_microsoft_third_party_login(user.id, claims)
        return await self._complete_admin_login(user)

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Refresh access token using refresh token.
        :param refresh_token:
        :return:
        """
        try:
            new_refresh, rt_data = await self._refresh_token_provider.rotate(refresh_token)
        except RefreshTokenInvalidException:
            raise UnauthorizedException(detail="Invalid refresh token")

        user = await self._admin_user_handler.get_user_detail_by_id(rt_data.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")

        roles = await self._admin_role_handler.init_user_roles_cache(user, self._expires_in)
        permissions = await self._admin_permission_handler.init_user_permissions_cache(user, self._expires_in)

        access_token = self._jwt_provider.create_access_token(
            user=user,
            family_id=rt_data.family_id,
            roles=roles,
            permissions=permissions,
            aud_type=AccessTokenAudType.ADMIN,
        )
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    async def logout(self, access_token: str, refresh_token: Optional[str]) -> None:
        """
        Logout user by revoking access and refresh tokens.
        :param access_token:
        :param refresh_token:
        :return:
        """
        payload: Optional[AccessTokenPayload] = self._jwt_provider.verify_token(
            token=access_token,
            is_admin=True,
        )
        if payload and payload.exp:
            exp_dt = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
            await self._token_blacklist_provider.add_to_blacklist(access_token, exp_dt)
        if refresh_token:
            await self._refresh_token_provider.revoke_by_token(refresh_token, revoke_family=True)

    async def admin_profile(self) -> AdminInfo:
        ctx: Optional[UserContext] = get_user_context()
        if not ctx or not ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        user = await self._admin_user_handler.get_user_detail_by_id(ctx.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")
        roles = await self._admin_role_handler.init_user_roles_cache(user, self._expires_in)
        return AdminInfo(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            roles=roles or [],
            preferred_locale_id=user.preferred_locale_id,
            last_login_at=user.last_login_at,
        )
