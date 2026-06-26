"""
Admin resource application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.application.rbac.commands import (
    ChangeResourceParentCommand,
    ChangeResourceSequenceCommand,
    CreateResourceCommand,
    DeleteCommand,
    ResourceListQueryCommand,
    UpdateResourceCommand,
)
from portal.application.rbac.results import (
    CreateIdResult,
    ResourceDetailResult,
    ResourceListResult,
    ResourceTreeResult,
)
from portal.domain.audit.constants import AUTH_RESOURCE_TABLE
from portal.domain.rbac.entities import ResourceItem, ResourceTreeNode
from portal.exceptions.responses import (
    ApiBaseException,
    ConflictErrorException,
    NotFoundException,
    UnauthorizedException,
)
from portal.domain.rbac.ports import RbacAuditPort, ResourceRepositoryPort
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context


class ResourceService:
    """Admin resource use cases."""

    def __init__(
        self,
        resource_repository: ResourceRepositoryPort,
        rbac_audit_service: RbacAuditPort,
    ):
        self._repository = resource_repository
        self._audit = rbac_audit_service
        self._user_ctx: UserContext = get_user_context()
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    async def _get_resource_audit_dict(self, resource_id: UUID) -> Optional[dict[str, Any]]:
        try:
            resource = await self.get_resource(resource_id=resource_id)
        except NotFoundException:
            return None
        return resource.model_dump(mode="json")

    def _build_translation_payloads(
        self,
        command: CreateResourceCommand | UpdateResourceCommand,
    ) -> list[dict[str, Any]]:
        return list(command.translations or [])

    def _translation_rows(
        self,
        resource_id: UUID,
        translation_payloads: list,
    ) -> list[dict[str, Any]]:
        return [
            dict(
                resource_id=resource_id,
                locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                name=item.name if hasattr(item, "name") else item["name"],
                description=item.description if hasattr(item, "description") else item.get("description"),
                remark=item.remark if hasattr(item, "remark") else item.get("remark"),
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(
        self,
        resource_id: UUID,
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
        rows = self._translation_rows(resource_id, translation_payloads)
        await self._repository.upsert_translations(rows)

    async def get_resource(self, resource_id: UUID) -> ResourceDetailResult:
        """
        Get resource by id.
        :param resource_id:
        :return:
        """
        resource = await self._repository.get_by_id(
            resource_id=resource_id,
            locale_id=self._resolved_locale_id(),
        )
        if not resource:
            raise NotFoundException(detail=f"Resource {resource_id} not found")
        return ResourceDetailResult.model_validate(resource.model_dump())

    async def create_resource(self, command: CreateResourceCommand) -> CreateIdResult:
        """
        Create a resource.
        :param command:
        :return:
        """
        resource_id = uuid.uuid4()
        try:
            await self._repository.insert_resource(
                {
                    "id": resource_id,
                    "pid": command.pid,
                    "key": command.key,
                    "code": command.code,
                    "icon": command.icon,
                    "path": command.path,
                    "type": command.type,
                    "is_visible": command.is_visible,
                }
            )
            await self._validate_and_upsert_translations(
                resource_id,
                self._build_translation_payloads(command),
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail=f"Resource {command.code} already exists",
                    debug_detail=str(error),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        self._audit.create_log(
            OperationType.CREATE,
            record_id=resource_id,
            operation_code=AUTH_RESOURCE_TABLE,
            new_data={
                **command.model_dump(mode="json", exclude_none=True),
                "id": str(resource_id),
            },
        )
        return CreateIdResult(id=resource_id)

    async def change_parent(self, resource_id: UUID, command: ChangeResourceParentCommand) -> None:
        """
        Change resource parent.
        :param resource_id:
        :param command:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            await self._repository.change_parent(resource_id, command.pid)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_row = await self._get_resource_audit_dict(resource_id)
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=resource_id,
            operation_code=AUTH_RESOURCE_TABLE,
            old_data=old_row,
            new_data=new_row,
        )

    async def update_resource(self, resource_id: UUID, command: UpdateResourceCommand) -> None:
        """
        Update a resource.
        :param resource_id:
        :param command:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            n = await self._repository.update_resource(
                resource_id,
                {
                    "pid": command.pid,
                    "key": command.key,
                    "code": command.code,
                    "icon": command.icon,
                    "path": command.path,
                    "type": command.type,
                    "is_visible": command.is_visible,
                },
            )
            if n == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Resource {resource_id} not found",
                )
            await self._validate_and_upsert_translations(
                resource_id,
                self._build_translation_payloads(command),
            )
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(
                    detail=f"Resource {command.code} already exists",
                    debug_detail=str(error),
                )
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_row = await self._get_resource_audit_dict(resource_id)
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=resource_id,
            operation_code=AUTH_RESOURCE_TABLE,
            old_data=old_row,
            new_data=new_row,
        )

    async def change_sequence(self, command: ChangeResourceSequenceCommand) -> None:
        """
        Swap sequence between two resources.
        :param command:
        :return:
        """
        old_row = await self._get_resource_audit_dict(command.id)
        old_another_row = await self._get_resource_audit_dict(command.another_id)
        try:
            await self._repository.update_sequence(command.id, command.another_sequence)
            await self._repository.update_sequence(command.another_id, command.sequence)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_row = await self._get_resource_audit_dict(command.id)
        new_another_row = await self._get_resource_audit_dict(command.another_id)
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=command.id,
            operation_code=AUTH_RESOURCE_TABLE,
            old_data=old_row,
            new_data=new_row,
        )
        self._audit.create_log(
            OperationType.UPDATE,
            record_id=command.another_id,
            operation_code=AUTH_RESOURCE_TABLE,
            old_data=old_another_row,
            new_data=new_another_row,
        )

    async def delete_resource(self, resource_id: UUID, command: DeleteCommand) -> None:
        """
        Soft or hard delete a resource (and children on soft delete).
        :param resource_id:
        :param command:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            if command.permanent:
                await self._repository.delete_hard(resource_id)
            else:
                await self._repository.delete_soft(resource_id, command.reason)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        if command.permanent:
            self._audit.create_log(
                OperationType.DELETE,
                record_id=resource_id,
                operation_code=AUTH_RESOURCE_TABLE,
                old_data=old_row,
                new_data={"deleted": True, "permanent": True},
            )
        else:
            new_row = await self._get_resource_audit_dict(resource_id)
            self._audit.create_log(
                OperationType.RECYCLE,
                record_id=resource_id,
                operation_code=AUTH_RESOURCE_TABLE,
                old_data=old_row,
                new_data=new_row,
            )

    async def restore_resource(self, resource_id: UUID) -> None:
        """
        Restore a resource and its direct children.
        :param resource_id:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            await self._repository.restore_resource_tree(resource_id)
        except Exception as error:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(error),
            )
        new_row = await self._get_resource_audit_dict(resource_id)
        self._audit.create_log(
            OperationType.RESTORE,
            record_id=resource_id,
            operation_code=AUTH_RESOURCE_TABLE,
            old_data=old_row,
            new_data=new_row,
        )

    @staticmethod
    def build_tree(items: list[ResourceItem]) -> list[ResourceTreeNode]:
        """
        Build a tree from flat resource items using id/pid relations.
        :param items:
        :return:
        """
        nodes = {item.id: ResourceTreeNode.model_validate(item.model_dump()) for item in items}
        root_items: list[ResourceTreeNode] = []
        for node in nodes.values():
            if node.pid and node.pid in nodes:
                if not nodes[node.pid].children:
                    nodes[node.pid].children = []
                nodes[node.pid].children.append(node)
            else:
                root_items.append(node)

        def sort_nodes(arr: list[ResourceTreeNode]) -> None:
            arr.sort(key=lambda n: (n.sequence, n.name))
            for n in arr:
                if n.children:
                    sort_nodes(n.children)

        sort_nodes(root_items)
        return root_items

    async def get_admin_resource_tree(self) -> ResourceTreeResult:
        """
        Hierarchical admin resource tree.
        :return:
        """
        if not self._user_ctx.user_id or (not self._user_ctx.is_superuser and not self._user_ctx.is_admin):
            raise UnauthorizedException()
        resources = await self.get_resource_menus()
        hierarchical_items = self.build_tree(resources)
        return ResourceTreeResult(items=hierarchical_items)

    async def get_resource_menus(self, is_deleted: bool = False) -> list[ResourceItem]:
        """
        Flat resource menu list.
        :param is_deleted:
        :return:
        """
        return await self._repository.list_menus(
            is_deleted=is_deleted,
            locale_id=self._resolved_locale_id(),
        )

    async def get_resource_by_user_id(self, user_id: UUID) -> list[ResourceItem]:
        """
        Resources visible to a user via role permissions.
        :param user_id:
        :return:
        """
        return await self._repository.list_by_user_id(
            user_id=user_id,
            locale_id=self._resolved_locale_id(),
        )

    async def get_resources(self, command: ResourceListQueryCommand) -> ResourceListResult:
        """
        Admin resource list filtered by deleted flag.
        :param command:
        :return:
        """
        if not self._user_ctx.user_id or not self._user_ctx.is_admin:
            raise UnauthorizedException()
        resources = await self.get_resource_menus(is_deleted=command.deleted)
        return ResourceListResult(items=resources)

    async def get_user_permission_menus(self) -> ResourceListResult:
        """
        Menus for the current admin user (superuser sees all).
        :return:
        """
        if not self._user_ctx.user_id or not self._user_ctx.is_admin:
            raise UnauthorizedException()
        if self._user_ctx.is_superuser:
            resource_items = await self.get_resource_menus()
        else:
            resource_items = await self.get_resource_by_user_id(user_id=self._user_ctx.user_id)
        return ResourceListResult(items=resource_items)
