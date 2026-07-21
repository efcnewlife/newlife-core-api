"""
Admin refresh token and logout application service.
"""
from datetime import datetime, timezone
from typing import Optional

from portal.application.auth.commands import LogoutCommand, RefreshTokenCommand
from portal.application.auth.mappers import normalize_user_for_token
from portal.application.auth.member_web_app_resolver import resolve_request_app_code
from portal.application.auth.results import AccessTokenPayload, TokenResult
from portal.application.rbac.permission_service import PermissionService
from portal.application.rbac.role_service import RoleService
from portal.config import settings
from portal.domain.auth.member_web_app import MemberWebAppRegistry
from portal.exceptions.responses import ForbiddenException, RefreshTokenInvalidException, UnauthorizedException
from portal.domain.auth.ports import UserRepositoryPort
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.tracing.distributed_trace import distributed_trace
from portal.providers.jwt_provider import JWTProvider
from portal.providers.member_refresh_app_binding_provider import MemberRefreshAppBindingProvider
from portal.providers.refresh_token_provider import RefreshTokenProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider


class RefreshTokenService:
    """Refresh and logout use cases."""

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        jwt_provider: JWTProvider,
        refresh_token_provider: RefreshTokenProvider,
        token_blacklist_provider: TokenBlacklistProvider,
        role_service: RoleService,
        permission_service: PermissionService,
        member_web_app_registry: Optional[MemberWebAppRegistry] = None,
        member_refresh_app_binding_provider: Optional[MemberRefreshAppBindingProvider] = None,
    ):
        self._expires_in = 60 * 60 * 24
        self._repository = user_repository
        self._jwt_provider = jwt_provider
        self._refresh_token_provider = refresh_token_provider
        self._token_blacklist_provider = token_blacklist_provider
        self._role_service = role_service
        self._permission_service = permission_service
        self._member_web_app_registry = member_web_app_registry
        self._member_refresh_app_binding_provider = member_refresh_app_binding_provider

    @distributed_trace()
    async def refresh_token(self, command: RefreshTokenCommand) -> TokenResult:
        try:
            new_refresh, rt_data = await self._refresh_token_provider.rotate(command.refresh_token)
        except RefreshTokenInvalidException:
            raise UnauthorizedException(detail="Invalid refresh token")

        user = await self._repository.get_sensitive_by_id(rt_data.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")

        token_user = normalize_user_for_token(user)
        roles = await self._role_service.init_user_roles_cache(token_user, self._expires_in)
        permissions = await self._permission_service.init_user_permissions_cache(
            token_user,
            self._expires_in,
        )

        access_token = self._jwt_provider.create_access_token(
            user=token_user,
            family_id=rt_data.family_id,
            roles=roles,
            permissions=permissions,
            aud_type=AccessTokenAudType.ADMIN,
        )
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return TokenResult(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    @distributed_trace()
    async def refresh_member_token(self, command: RefreshTokenCommand) -> TokenResult:
        if not self._member_web_app_registry or not self._member_refresh_app_binding_provider:
            raise UnauthorizedException(detail="Member auth is not configured")

        request_app_code = resolve_request_app_code(self._member_web_app_registry, required=True)
        try:
            new_refresh, rt_data = await self._refresh_token_provider.rotate(command.refresh_token)
        except RefreshTokenInvalidException:
            raise UnauthorizedException(detail="Invalid refresh token")

        bound_app_code = await self._member_refresh_app_binding_provider.get_app_code(rt_data.family_id)
        if not bound_app_code:
            raise UnauthorizedException(detail="Invalid refresh token binding")
        if bound_app_code != request_app_code:
            raise ForbiddenException(detail="Refresh token cannot be used from this web app")

        await self._member_refresh_app_binding_provider.bind(rt_data.family_id, bound_app_code)

        user = await self._repository.get_sensitive_by_id(rt_data.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")
        if not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the app")

        token_user = normalize_user_for_token(user)
        access_token = self._jwt_provider.create_access_token(
            user=token_user,
            family_id=rt_data.family_id,
            aud_type=AccessTokenAudType.USER,
            azp=bound_app_code,
        )
        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        return TokenResult(
            access_token=access_token,
            refresh_token=new_refresh,
            token_type="bearer",
            expires_in=expires_in,
        )

    @distributed_trace()
    async def logout(self, command: LogoutCommand) -> None:
        payload: Optional[AccessTokenPayload] = self._jwt_provider.verify_token(
            token=command.access_token,
            is_admin=True,
        )
        if payload and payload.exp:
            exp_dt = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
            await self._token_blacklist_provider.add_to_blacklist(command.access_token, exp_dt)
        if command.refresh_token:
            await self._refresh_token_provider.revoke_by_token(
                command.refresh_token,
                revoke_family=True,
            )

    @distributed_trace()
    async def logout_member(self, command: LogoutCommand) -> None:
        payload: Optional[AccessTokenPayload] = self._jwt_provider.verify_token(
            token=command.access_token,
            is_admin=False,
        )
        if payload and payload.exp:
            exp_dt = datetime.fromtimestamp(payload.exp, tz=timezone.utc)
            await self._token_blacklist_provider.add_to_blacklist(command.access_token, exp_dt)
            if payload.family_id and self._member_refresh_app_binding_provider:
                await self._member_refresh_app_binding_provider.clear(payload.family_id)
        if command.refresh_token:
            await self._refresh_token_provider.revoke_by_token(
                command.refresh_token,
                revoke_family=True,
            )
