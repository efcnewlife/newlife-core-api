"""
Admin permission application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.domain.rbac.ports import PermissionCachePort, PermissionRepositoryPort, RbacAuditPort
from portal.infrastructure.cache.permission_cache import PermissionCache
from portal.libs.tracing.distributed_trace import distributed_trace
from portal.application.auth.results import UserSensitive
from portal.application.rbac.commands import (
    BulkIdsCommand,
    CreatePermissionCommand,
    DeleteCommand,
    PermissionPagesQueryCommand,
    UpdatePermissionCommand,
)
from portal.application.rbac.results import (
    CreateIdResult,
    PermissionDetailResult,
    PermissionListResult,
    PermissionPageResult,
)
from portal.domain.audit.constants import AUTH_PERMISSION_TABLE
from portal.exceptions.responses import ApiBaseException, ConflictErrorException
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import RequestContext, get_request_context


class PermissionService:
    """Admin permission use cases."""

    def __init__(
        self,
        permission_repository: PermissionRepositoryPort,
        permission_cache: PermissionCachePort,
        rbac_audit_service: RbacAuditPort,
    ):
        self._repository = permission_repository
        self._cache = permission_cache
        self._audit = rbac_audit_service
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @staticmethod
    def permission_key(user_id: UUID, permission_code: Optional[str] = None) -> str:
        return PermissionCache.permission_key(user_id=user_id, permission_code=permission_code)

    async def _get_permission_audit_dict(self, permission_id: UUID) -> Optional[dict[str, Any]]:
        permission = await self.get_permission_by_id(permission_id)
        if not permission:
            return None
        return permission.model_dump(mode="json")

    def _build_translation_payloads(
        self,
        command: CreatePermissionCommand | UpdatePermissionCommand,
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
        permission_id: UUID,
        translation_payloads: list,
    ) -> list[dict[str, Any]]:
        return [
            dict(
                permission_id=permission_id,
                locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                name=item.name if hasattr(item, "name") else item["name"],
                description=item.description if hasattr(item, "description") else item.get("description"),
                remark=item.remark if hasattr(item, "remark") else item.get("remark"),
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(
        self,
        permission_id: UUID,
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
        rows = self._translation_rows(permission_id, translation_payloads)
        await self._repository.upsert_translations(rows)

    @distributed_trace()
    async def init_user_permissions_cache(
        self,
        user: UserSensitive,
        expire: int,
    ) -> Optional[list[str]]:
        """
        Initialize user permissions cache.
        :param user:
        :param expire:
        :return:
        """
        if user.is_superuser:
            permissions = await self._repository.list_all_permissions()
        else:
            permissions = await self._repository.list_user_role_permissions(user.id)
        if not permissions:
            await self._cache.clear_user_permissions_cache(user_id=user.id)
            return None
        return await self._cache.init_user_permissions_cache(
            user_id=user.id,
            permissions=permissions,
            expire=expire,
        )

    async def clear_user_permissions_cache(self, user_id: UUID) -> None:
        """
        Clear user permissions cache.
        :param user_id:
        :return:
        """
        await self._cache.clear_user_permissions_cache(user_id=user_id)

    @distributed_trace()
    async def get_permission_by_id(self, permission_id: UUID) -> Optional[PermissionDetailResult]:
        """
        Get permission by id.
        :param permission_id:
        :return:
        """
        row = await self._repository.get_by_id(
            permission_id=permission_id,
            locale_id=self._resolved_locale_id(),
        )
        if row is None:
            return None
        return PermissionDetailResult.model_validate(row.model_dump())

    @distributed_trace()
    async def get_permission_pages(self, command: PermissionPagesQueryCommand) -> PermissionPageResult:
        """
        Paginated admin permissions.
        :param command:
        :return:
        """
        items, count = await self._repository.fetch_pages(
            command=command,
            locale_id=self._resolved_locale_id(),
        )
        return PermissionPageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    @distributed_trace()
    async def create_permission(self, command: CreatePermissionCommand) -> CreateIdResult:
        """
        Create a permission.
        :param command:
        :return:
        """
        permission_id = uuid.uuid4()
        try:
            await self._repository.insert_permission(
                {
                    "id": permission_id,
                    "code": command.code,
                    "resource_id": command.resource_id,
                    "verb_id": command.verb_id,
                    "is_active": command.is_active,
                }
            )
            await self._validate_and_upsert_translations(
                permission_id,
                self._build_translation_payloads(command),
            )
        except Exception as e:
            if self._repository.is_unique_violation(e):
                raise ConflictErrorException(
                    detail=f"Permission {command.code} already exists",
                    debug_detail=str(e),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        self._audit.create_log(
            OperationType.CREATE,
            record_id=permission_id,
            operation_code=AUTH_PERMISSION_TABLE,
            new_data={
                **command.model_dump(mode="json", exclude_none=True),
                "id": str(permission_id),
            },
        )
        return CreateIdResult(id=permission_id)

    async def update_permission(self, permission_id: UUID, command: UpdatePermissionCommand) -> None:
        """
        Update a permission.
        :param permission_id:
        :param command:
        :return:
        """
        old_row = await self._get_permission_audit_dict(permission_id)
        try:
            n = await self._repository.update_permission(
                permission_id,
                {
                    "code": command.code,
                    "resource_id": command.resource_id,
                    "verb_id": command.verb_id,
                    "is_active": command.is_active,
                },
            )
            if n == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Permission {permission_id} not found",
                )
            await self._validate_and_upsert_translations(
                permission_id,
                self._build_translation_payloads(command),
            )
        except ApiBaseException:
            raise
        except Exception as e:
            if self._repository.is_unique_violation(e):
                raise ConflictErrorException(
                    detail=f"Permission {command.code} already exists",
                    debug_detail=str(e),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        new_row = await self._get_permission_audit_dict(permission_id)
        if old_row is not None and new_row is not None:
            self._audit.create_log(
                OperationType.UPDATE,
                record_id=permission_id,
                operation_code=AUTH_PERMISSION_TABLE,
                old_data=old_row,
                new_data=new_row,
            )

    async def delete_permission(self, permission_id: UUID, command: DeleteCommand) -> None:
        """
        Delete a permission.
        :param permission_id:
        :param command:
        :return:
        """
        old_row = await self._get_permission_audit_dict(permission_id)
        try:
            if command.permanent:
                n = await self._repository.delete_hard(permission_id)
            else:
                n = await self._repository.delete_soft(permission_id, command.reason)
            if n == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Permission {permission_id} not found",
                )
        except ApiBaseException:
            raise
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        if command.permanent:
            self._audit.create_log(
                OperationType.DELETE,
                record_id=permission_id,
                operation_code=AUTH_PERMISSION_TABLE,
                old_data=old_row,
                new_data={"deleted": True, "permanent": True},
            )
        else:
            base = dict(old_row) if old_row else {"id": str(permission_id)}
            self._audit.create_log(
                OperationType.RECYCLE,
                record_id=permission_id,
                operation_code=AUTH_PERMISSION_TABLE,
                old_data=old_row,
                new_data={
                    **base,
                    "is_deleted": True,
                    "delete_reason": command.reason,
                },
            )

    async def restore_permission(self, command: BulkIdsCommand) -> None:
        """
        Restore permissions.
        :param command:
        :return:
        """
        try:
            await self._repository.restore_permissions(command.ids)
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        self._audit.create_log(
            OperationType.RESTORE,
            operation_code=AUTH_PERMISSION_TABLE,
            old_data={"permission_ids": [str(item) for item in command.ids]},
            new_data={"is_deleted": False, "delete_reason": None},
        )

    @distributed_trace()
    async def get_permission_list(self) -> PermissionListResult:
        """
        Cached permission list for current locale.
        :return:
        """
        locale_id = self._resolved_locale_id()
        if not locale_id:
            return PermissionListResult(items=[])
        cached = await self._cache.get_permission_list_json(locale_id)
        if cached:
            return PermissionListResult.model_validate_json(cached)
        permissions = await self._repository.list_for_locale(locale_id)
        result = PermissionListResult(items=permissions)
        await self._cache.set_permission_list_json(locale_id, result.model_dump_json())
        return result
