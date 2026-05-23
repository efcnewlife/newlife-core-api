"""
Admin role application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.application.auth.results import UserSensitive
from portal.application.rbac.commands import (
    AssignRolePermissionsCommand,
    CreateRoleCommand,
    DeleteCommand,
    PagesQueryCommand,
    UpdateRoleCommand,
)
from portal.application.rbac.results import (
    CreateIdResult,
    RoleDetailResult,
    RoleListResult,
    RolePageResult,
)
from portal.domain.audit.constants import AUTH_ROLE_PERMISSION_TABLE, AUTH_ROLE_TABLE
from portal.exceptions.responses import ApiBaseException, ConflictErrorException
from portal.domain.rbac.ports import RbacAuditPort, RoleCachePort, RoleRepositoryPort
from portal.infrastructure.cache.role_cache import RoleCache
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import RequestContext, get_request_context


class RoleService:
    """Admin role use cases."""

    def __init__(
        self,
        role_repository: RoleRepositoryPort,
        role_cache: RoleCachePort,
        rbac_audit_service: RbacAuditPort,
    ):
        self._repository = role_repository
        self._cache = role_cache
        self._audit = rbac_audit_service
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @staticmethod
    def user_role_key(user_id: UUID) -> str:
        return RoleCache.user_role_key(user_id=user_id)

    async def _get_role_audit_dict(self, role_id: UUID) -> Optional[dict[str, Any]]:
        role = await self.get_role_by_id(role_id)
        if not role:
            return None
        return role.model_dump(mode="json")

    def _build_translation_payloads(
        self,
        command: CreateRoleCommand | UpdateRoleCommand,
    ) -> list[dict[str, Any]]:
        translation_payloads = command.translations or []
        if (
            not translation_payloads
            and command.name
            and self._req_ctx
            and self._req_ctx.resolved_locale_id
        ):
            translation_payloads = [
                {
                    "locale_id": self._req_ctx.resolved_locale_id,
                    "name": command.name,
                    "description": command.description,
                    "remark": command.remark,
                }
            ]
        return translation_payloads

    def _translation_rows(
        self,
        role_id: UUID,
        translation_payloads: list,
    ) -> list[dict[str, Any]]:
        return [
            dict(
                role_id=role_id,
                locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                name=item.name if hasattr(item, "name") else item["name"],
                description=item.description if hasattr(item, "description") else item.get("description"),
                remark=item.remark if hasattr(item, "remark") else item.get("remark"),
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(
        self,
        role_id: UUID,
        translation_payloads: list,
    ) -> None:
        if not translation_payloads:
            return
        locale_ids = [
            item.locale_id if hasattr(item, "locale_id") else item["locale_id"]
            for item in translation_payloads
        ]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise ApiBaseException(
                status_code=422,
                detail="Invalid or inactive locale_id in translations",
            )
        rows = self._translation_rows(role_id, translation_payloads)
        await self._repository.upsert_translations(rows)

    async def init_user_roles_cache(
        self,
        user: UserSensitive,
        expire: int,
    ) -> Optional[list[str]]:
        """
        Initialize user roles cache.
        :param user:
        :param expire:
        :return:
        """
        if user.is_superuser:
            role_codes = ["superadmin"]
        else:
            role_codes = await self._repository.list_user_role_codes(user.id)
        if not role_codes:
            await self._cache.clear_user_roles_cache(user_id=user.id)
            return None
        return await self._cache.init_user_roles_cache(
            user_id=user.id,
            role_codes=role_codes,
            expire=expire,
        )

    async def clear_user_roles_cache(self, user_id: UUID) -> None:
        """
        Clear user roles cache.
        :param user_id:
        :return:
        """
        await self._cache.clear_user_roles_cache(user_id=user_id)

    async def get_role_pages(self, command: PagesQueryCommand) -> RolePageResult:
        """
        Paginated admin roles.
        :param command:
        :return:
        """
        items, count = await self._repository.fetch_pages(
            model=command,
            locale_id=self._resolved_locale_id(),
        )
        return RolePageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    async def get_active_roles(self) -> RoleListResult:
        """
        Active roles for admin dropdown.
        :return:
        """
        if not self._resolved_locale_id():
            return RoleListResult(items=[])
        roles = await self._repository.list_active_roles(locale_id=self._resolved_locale_id())
        return RoleListResult(items=roles)

    async def get_role_by_id(self, role_id: UUID) -> Optional[RoleDetailResult]:
        """
        Get role by id.
        :param role_id:
        :return:
        """
        role = await self._repository.get_by_id(
            role_id=role_id,
            locale_id=self._resolved_locale_id(),
        )
        if not role:
            return None
        return RoleDetailResult.model_validate(role.model_dump())

    async def create_role(self, command: CreateRoleCommand) -> CreateIdResult:
        """
        Create a role.
        :param command:
        :return:
        """
        role_id = uuid.uuid4()
        try:
            await self._repository.insert_role(
                {
                    "id": role_id,
                    "code": command.code,
                    "is_active": command.is_active,
                }
            )
            await self._validate_and_upsert_translations(
                role_id,
                self._build_translation_payloads(command),
            )
            await self._repository.insert_role_permissions(role_id, command.permissions)
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail="Role code already exists",
                    debug_detail=str(error),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        self._audit.create_log(
            OperationType.CREATE,
            record_id=role_id,
            operation_code=AUTH_ROLE_TABLE,
            new_data={
                **command.model_dump(mode="json", exclude_none=True, exclude={"permissions"}),
                "id": str(role_id),
            },
        )
        self._audit.create_log(
            OperationType.CREATE,
            record_id=role_id,
            operation_code=AUTH_ROLE_PERMISSION_TABLE,
            new_data={
                "role_id": str(role_id),
                "permission_ids": [str(item) for item in command.permissions],
            },
        )
        return CreateIdResult(id=role_id)

    async def update_role(self, role_id: UUID, command: UpdateRoleCommand) -> None:
        """
        Update a role.
        :param role_id:
        :param command:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        old_permission_ids = await self._repository.fetch_permission_ids_for_role(role_id)
        try:
            affected = await self._repository.upsert_role(
                role_id,
                {
                    "code": command.code,
                    "is_active": command.is_active,
                },
            )
            await self._validate_and_upsert_translations(
                role_id,
                self._build_translation_payloads(command),
            )
            new_permission_ids = set(command.permissions or [])
            old_permission_id_set = set(old_permission_ids)
            insert_permission_ids = list(new_permission_ids - old_permission_id_set)
            delete_permission_ids = list(old_permission_id_set - new_permission_ids)
            await self._repository.insert_role_permissions(role_id, insert_permission_ids)
            await self._repository.delete_role_permissions(role_id, delete_permission_ids)
            if affected == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Role {role_id} not found",
                )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail="Role code already exists",
                    debug_detail=str(error),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_role_row = await self._get_role_audit_dict(role_id)
        if old_role_row is not None and new_role_row is not None:
            self._audit.create_log(
                OperationType.UPDATE,
                record_id=role_id,
                operation_code=AUTH_ROLE_TABLE,
                old_data=old_role_row,
                new_data=new_role_row,
            )
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=role_id,
            operation_code=AUTH_ROLE_PERMISSION_TABLE,
            old_data={
                "role_id": str(role_id),
                "permission_ids": [str(item) for item in old_permission_ids],
            },
            new_data={
                "role_id": str(role_id),
                "permission_ids": [str(item) for item in command.permissions or []],
            },
        )

    async def delete_role(self, role_id: UUID, command: DeleteCommand) -> None:
        """
        Delete a role.
        :param role_id:
        :param command:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        old_permission_ids = await self._repository.fetch_permission_ids_for_role(role_id)
        try:
            if command.permanent:
                await self._repository.delete_hard(role_id)
            else:
                await self._repository.delete_soft(role_id, command.reason)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        if command.permanent:
            self._audit.create_log(
                OperationType.DELETE,
                record_id=role_id,
                operation_code=AUTH_ROLE_TABLE,
                old_data=old_role_row,
                new_data={"deleted": True, "permanent": True},
            )
            self._audit.create_log(
                OperationType.DELETE,
                record_id=role_id,
                operation_code=AUTH_ROLE_PERMISSION_TABLE,
                old_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in old_permission_ids],
                },
                new_data={"role_id": str(role_id), "permission_ids": []},
            )
        else:
            base = dict(old_role_row) if old_role_row else {"id": str(role_id)}
            self._audit.create_log(
                OperationType.RECYCLE,
                record_id=role_id,
                operation_code=AUTH_ROLE_TABLE,
                old_data=old_role_row,
                new_data={
                    **base,
                    "is_deleted": True,
                    "delete_reason": command.reason,
                },
            )

    async def restore_role(self, role_id: UUID) -> None:
        """
        Restore a soft-deleted role.
        :param role_id:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        try:
            await self._repository.restore_role(role_id)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_role_row = await self._get_role_audit_dict(role_id)
        self._audit.create_log(
            OperationType.RESTORE,
            record_id=role_id,
            operation_code=AUTH_ROLE_TABLE,
            old_data=old_role_row,
            new_data=new_role_row,
        )

    async def assign_role_permissions(self, role_id: UUID, command: AssignRolePermissionsCommand) -> None:
        """
        Assign or revoke permissions for a role.
        :param role_id:
        :param command:
        :return:
        """
        original_permissions = await self._repository.fetch_permission_ids_for_role(role_id)
        insert_permissions = [
            {
                "role_id": role_id,
                "permission_id": permission_id,
            }
            for permission_id in command.permission_ids
            if permission_id not in original_permissions
        ]
        delete_permissions = [
            permission_id
            for permission_id in original_permissions
            if permission_id not in command.permission_ids
        ]
        try:
            await self._repository.insert_role_permission_rows(insert_permissions)
            await self._repository.delete_role_permissions(role_id, delete_permissions)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=role_id,
            operation_code=AUTH_ROLE_PERMISSION_TABLE,
            old_data={
                "role_id": str(role_id),
                "permission_ids": [str(item) for item in original_permissions],
            },
            new_data={
                "role_id": str(role_id),
                "permission_ids": [str(item) for item in command.permission_ids],
            },
        )
