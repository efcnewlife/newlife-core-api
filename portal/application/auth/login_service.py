"""
Admin login and profile application service.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from portal.application.auth.commands import LoginCommand, LoginWithoutValidateCommand
from portal.application.auth.mappers import normalize_user_for_token
from portal.application.auth.results import (
    AdminProfileResult,
    LoginResult,
    TokenResult,
    UserSensitive,
)
from portal.application.rbac.permission_service import PermissionService
from portal.application.rbac.role_service import RoleService
from portal.config import settings
from portal.exceptions.responses import UnauthorizedException
from portal.domain.auth.ports import UserRepositoryPort
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace
from portal.providers.jwt_provider import JWTProvider
from portal.providers.password_provider import PasswordProvider
from portal.providers.refresh_token_provider import RefreshTokenProvider


class LoginService:
    """Password login and admin profile use cases."""

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        jwt_provider: JWTProvider,
        refresh_token_provider: RefreshTokenProvider,
        password_provider: PasswordProvider,
        role_service: RoleService,
        permission_service: PermissionService,
    ):
        self._expires_in = 60 * 60 * 24
        self._repository = user_repository
        self._jwt_provider = jwt_provider
        self._refresh_token_provider = refresh_token_provider
        self._password_provider = password_provider
        self._role_service = role_service
        self._permission_service = permission_service

    @distributed_trace()
    async def login_with_password(self, command: LoginCommand) -> LoginResult:
        user = await self._repository.get_sensitive_by_email(command.email)
        if not user or not user.password_hash:
            raise UnauthorizedException(detail="Invalid email or password")
        if not self._password_provider.verify_password(command.password, user.password_hash):
            raise UnauthorizedException(detail="Invalid email or password")
        return await self.complete_admin_login(user)

    @distributed_trace()
    async def complete_admin_login(self, user: UserSensitive) -> LoginResult:
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")

        token_user = normalize_user_for_token(user)
        roles = await self._role_service.init_user_roles_cache(token_user, self._expires_in)
        permissions = await self._permission_service.init_user_permissions_cache(
            token_user,
            self._expires_in,
        )

        family_id = uuid4()
        device_id = uuid4()
        access_token = self._jwt_provider.create_access_token(
            user=token_user,
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
        await self._repository.update_last_login_at(user_id=user.id, last_login_at=now)

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = TokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )
        admin = AdminProfileResult(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            roles=roles or [],
            preferred_locale_id=user.preferred_locale_id,
            last_login_at=user.last_login_at,
        )
        return LoginResult(admin=admin, token=token)

    @distributed_trace()
    async def admin_profile(self) -> AdminProfileResult:
        ctx: Optional[UserContext] = get_user_context()
        if not ctx or not ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        user = await self._repository.get_sensitive_by_id(ctx.user_id)
        if not user:
            raise UnauthorizedException(detail="User not found")
        token_user = normalize_user_for_token(user)
        roles = await self._role_service.init_user_roles_cache(token_user, self._expires_in)
        return AdminProfileResult(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            roles=roles or [],
            preferred_locale_id=user.preferred_locale_id,
            last_login_at=user.last_login_at,
        )

    @distributed_trace()
    async def login_without_validate(
        self,
        command: LoginWithoutValidateCommand,
        device_id: UUID,
    ) -> LoginResult:
        """
        Dev-only login that skips password validation.
        :param command:
        :param device_id:
        :return:
        """
        user = await self._repository.get_sensitive_by_email(command.email)
        if not user:
            raise UnauthorizedException(detail="Invalid email or password")
        if not user.is_admin or not user.verified or not user.is_active:
            raise UnauthorizedException(detail="User is not allowed to access the admin portal")

        token_user = normalize_user_for_token(user)
        roles = await self._role_service.init_user_roles_cache(token_user, self._expires_in)
        permissions = await self._permission_service.init_user_permissions_cache(
            token_user,
            self._expires_in,
        )

        family_id = uuid4()
        access_token = self._jwt_provider.create_access_token(
            user=token_user,
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
        await self._repository.update_last_login_at(user_id=user.id, last_login_at=now)

        expires_in = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        token = TokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=expires_in,
        )
        admin = AdminProfileResult(
            id=user.id,
            email=user.email or "",
            first_name=user.first_name or "",
            last_name=user.last_name or "",
            roles=roles or [],
            preferred_locale_id=user.preferred_locale_id,
            last_login_at=user.last_login_at,
        )
        return LoginResult(admin=admin, token=token)
