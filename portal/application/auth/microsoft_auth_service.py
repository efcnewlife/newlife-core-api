"""
Microsoft Entra ID admin login application service.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import jwt
from fastapi import status

from portal.application.auth.commands import MicrosoftLoginCommand
from portal.application.auth.login_service import LoginService
from portal.application.auth.member_web_app_resolver import resolve_request_app_code
from portal.application.auth.microsoft_profile_mapper import profile_fields_from_microsoft_claims
from portal.application.auth.results import LoginResult, MemberLoginResult, UserSensitive
from portal.config import settings
from portal.domain.auth.member_web_app import MemberWebAppRegistry
from portal.domain.auth.ports import UserRepositoryPort
from portal.exceptions.responses import ApiBaseException, UnauthorizedException
from portal.libs.consts.enums import ThirdPartyProvider
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace
from portal.providers.microsoft_oidc_provider import MicrosoftOidcProvider


class MicrosoftAuthService:
    """Microsoft OIDC login use cases."""

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        microsoft_oidc_provider: MicrosoftOidcProvider,
        login_service: LoginService,
        member_web_app_registry: Optional[MemberWebAppRegistry] = None,
    ):
        self._repository = user_repository
        self._microsoft_oidc_provider = microsoft_oidc_provider
        self._login_service = login_service
        self._member_web_app_registry = member_web_app_registry

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
            await self._repository.upsert_auth_user_third_party(
                user_id=user_id,
                provider=ThirdPartyProvider.MICROSOFT,
                provider_uid=provider_uid,
                provider_tenant_id=tenant_uuid,
                additional_data=additional_data,
                token_expires_at=token_expires_at,
            )
        except Exception:
            logger.exception("Failed to upsert AuthUserThirdParty for Microsoft login")

    async def _ensure_user_profile(self, user_id: UUID, claims: dict[str, Any]) -> None:
        if await self._repository.user_profile_exists(user_id):
            return
        first_name, last_name, preferred_name = profile_fields_from_microsoft_claims(claims)
        try:
            await self._repository.create_user_profile(user_id=user_id, first_name=first_name, last_name=last_name, preferred_name=preferred_name)
        except Exception:
            logger.exception("Failed to create AuthUserProfile for Microsoft login user_id=%s", user_id)
            raise

    @distributed_trace()
    async def microsoft_login(self, command: MicrosoftLoginCommand) -> LoginResult:
        user = await self._resolve_microsoft_user(command)
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")
        return await self._login_service.complete_admin_login(user)

    async def _resolve_microsoft_user(self, command: MicrosoftLoginCommand) -> UserSensitive:
        if not self._microsoft_oidc_provider.is_configured():
            raise ApiBaseException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Microsoft OIDC is not configured")
        try:
            claims: dict[str, Any] = self._microsoft_oidc_provider.verify_id_token(command.id_token)
        except jwt.PyJWTError:
            raise UnauthorizedException(detail="Invalid Microsoft token")

        email_raw = claims.get("upn")
        if not email_raw:
            raise UnauthorizedException(detail="Invalid Microsoft token: missing upn claim")
        email = str(email_raw).strip().lower()

        user: Optional[UserSensitive] = await self._repository.get_sensitive_by_email(email)
        if not user:
            user = await self._repository.get_sensitive_by_email_without_profile(email)
            if not user:
                raise UnauthorizedException(detail="User not found")
            await self._ensure_user_profile(user.id, claims)
            user = await self._repository.get_sensitive_by_email(email)
            if not user:
                raise UnauthorizedException(detail="User not found")
        await self._record_microsoft_third_party_login(user.id, claims)
        return user

    @distributed_trace()
    async def microsoft_member_login(self, command: MicrosoftLoginCommand) -> MemberLoginResult:
        if not self._member_web_app_registry:
            raise ApiBaseException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Member web app registry is not configured")
        app_code = resolve_request_app_code(self._member_web_app_registry, required=True)
        user = await self._resolve_microsoft_user(command)
        if not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the app")
        return await self._login_service.complete_member_login(user, app_code=app_code)
