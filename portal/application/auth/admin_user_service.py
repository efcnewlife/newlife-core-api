"""
Admin user application service.
"""
import uuid
from typing import Optional
from uuid import UUID

from portal.application.auth.results import UserSensitive
from portal.application.rbac.commands import (
    AdminUserPagesQueryCommand,
    BindUserRolesCommand,
    BulkIdsCommand,
    ChangePasswordCommand,
    CreateAdminUserCommand,
    DeleteCommand,
    UpdateAdminUserCommand,
)
from portal.application.rbac.permission_service import PermissionService
from portal.application.rbac.results import (
    AdminUserDetailResult,
    AdminUserListResult,
    AdminUserPageResult,
    AdminUserRolesResult,
    CreateIdResult,
)
from portal.application.rbac.role_service import RoleService
from portal.exceptions.responses import (
    UnauthorizedException,
    BadRequestException,
)
from portal.domain.auth.ports import UserRepositoryPort
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.providers.password_provider import PasswordProvider


class AdminUserService:
    """Admin user CRUD and role binding use cases."""

    def __init__(
        self,
        user_repository: UserRepositoryPort,
        password_provider: PasswordProvider,
        role_service: RoleService,
        permission_service: PermissionService,
    ):
        self._repository = user_repository
        self._password_provider = password_provider
        self._role_service = role_service
        self._permission_service = permission_service
        self._user_ctx: Optional[UserContext] = get_user_context()

    async def get_user_detail_by_id(self, user_id: UUID) -> Optional[UserSensitive]:
        return await self._repository.get_sensitive_by_id(user_id)

    async def get_user_detail_by_email(self, email: str) -> Optional[UserSensitive]:
        return await self._repository.get_sensitive_by_email(email)

    async def get_user_pages(self, command: AdminUserPagesQueryCommand) -> AdminUserPageResult:
        items, count = await self._repository.get_user_pages(command)
        return AdminUserPageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    async def get_user_list(self, keyword: Optional[str] = None) -> AdminUserListResult:
        users = await self._repository.get_user_list(keyword=keyword)
        return AdminUserListResult(items=users)

    async def get_user_list_with_device_token(self, keyword: Optional[str] = None) -> AdminUserListResult:
        return await self.get_user_list(keyword=keyword)

    async def get_user_by_id(self, user_id: UUID) -> Optional[AdminUserDetailResult]:
        user = await self._repository.get_user_by_id(user_id)
        if not user:
            return None
        return AdminUserDetailResult.model_validate(user.model_dump())

    async def get_current_user(self) -> Optional[AdminUserDetailResult]:
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        return await self.get_user_by_id(self._user_ctx.user_id)

    async def create_user(self, command: CreateAdminUserCommand) -> CreateIdResult:
        if command.password != command.password_confirm:
            raise BadRequestException(detail="Passwords do not match")
        if not self._password_provider.validate_password(command.password):
            raise BadRequestException(detail="Password is not valid")
        user_id = uuid.uuid4()
        password_hash = self._password_provider.hash_password(command.password)
        return await self._repository.create_user(
            user_id=user_id,
            model=command,
            password_hash=password_hash,
        )

    async def update_current_user(self, command: UpdateAdminUserCommand) -> None:
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        await self.update_user(user_id=self._user_ctx.user_id, command=command)

    async def update_user(self, user_id: UUID, command: UpdateAdminUserCommand) -> None:
        await self._repository.update_user(user_id=user_id, model=command)

    async def delete_user(self, user_id: UUID, command: DeleteCommand) -> None:
        await self._repository.delete_user(user_id=user_id, model=command)

    async def restore_user(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            raise BadRequestException(detail="No user ids provided")
        await self._repository.restore_users(user_ids=command.ids)

    async def get_user_roles(self, user_id: UUID) -> AdminUserRolesResult:
        roles = await self._repository.get_user_role_ids(user_id)
        return AdminUserRolesResult(role_ids=roles)

    async def bind_roles(self, user_id: UUID, command: BindUserRolesCommand) -> None:
        await self._repository.bind_roles(user_id=user_id, role_ids=command.role_ids or [])
        await self._role_service.clear_user_roles_cache(user_id=user_id)
        await self._permission_service.clear_user_permissions_cache(user_id=user_id)

    async def change_password(self, user_id: UUID, command: ChangePasswordCommand) -> None:
        user = await self.get_user_detail_by_id(user_id=user_id)
        if not user:
            raise BadRequestException(detail="User not found")
        if not self._user_ctx or user.id != self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        if not self._password_provider.verify_password(command.old_password, user.password_hash):
            raise BadRequestException(detail="Old password is not valid")
        if command.new_password != command.new_password_confirm:
            raise BadRequestException(detail="New passwords do not match")
        if not self._password_provider.validate_password(command.new_password):
            raise BadRequestException(detail="New password is not valid")
        password_hash = self._password_provider.hash_password(command.new_password)
        await self._repository.update_password_hash(user_id=user_id, password_hash=password_hash)

    async def update_current_user_preferred_locale(self, preferred_locale_id: UUID) -> None:
        if not self._user_ctx or not self._user_ctx.user_id:
            raise UnauthorizedException(detail="Unauthorized")
        if not await self._repository.locale_exists(preferred_locale_id):
            raise BadRequestException(detail="Preferred language is invalid")
        await self._repository.update_preferred_locale(
            user_id=self._user_ctx.user_id,
            preferred_locale_id=preferred_locale_id,
        )
