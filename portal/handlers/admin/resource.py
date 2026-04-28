"""
Handler for admin resource
"""
import asyncio
import uuid
from typing import Any, Optional

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from redis.asyncio import Redis
from sqlalchemy.orm import aliased

from portal.config import settings
from portal.exceptions.responses import ApiBaseException, ConflictErrorException, UnauthorizedException, NotFoundException
from portal.handlers.admin.log import AdminLogHandler
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import get_request_context, RequestContext
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.database import Session, RedisPool
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthResource,
    AuthResourceTranslation,
    AuthPermission,
    AuthRole,
    AuthUser,
    AuthRolePermission,
    SystemLocale,
)
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.base import DeleteQueryBaseModel
from portal.serializers.admin.v1.resource import (
    AdminResourceCreate,
    AdminResourceUpdate,
    AdminResourceChangeSequence,
    AdminResourceItem,
    AdminResourceTree,
    AdminResourceTreeItem,
    AdminResourceList,
    AdminResourceDetail,
    AdminResourceChangeParent,
)


class AdminResourceHandler:
    """AdminResourceHandler"""

    def __init__(
        self,
        session: Session,
        redis_client: RedisPool,
        log_handler: AdminLogHandler,
    ):
        self._session = session
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._log_handler = log_handler
        self._user_ctx: UserContext = get_user_context()
        self._req_ctx: Optional[RequestContext] = get_request_context()

    async def _get_resource_audit_dict(self, resource_id: uuid.UUID) -> Optional[dict[str, Any]]:
        try:
            resource = await self.get_resource(resource_id=resource_id)
        except NotFoundException:
            return None
        return resource.model_dump(mode="json")

    async def get_resource(self, resource_id: uuid.UUID) -> AdminResourceDetail:
        """

        :param resource_id:
        :return:
        """
        pr_parent = aliased(AuthResource)
        parent_res_tr = aliased(AuthResourceTranslation)
        query = (
            self._session.select(
                AuthResource.id,
                sa.func.coalesce(AuthResourceTranslation.name, "").label("name"),
                AuthResource.key,
                AuthResource.code,
                AuthResource.icon,
                AuthResource.path,
                AuthResource.type,
                AuthResourceTranslation.remark,
                AuthResourceTranslation.description,
                AuthResource.sequence,
                AuthResource.is_deleted,
                sa.func.json_build_object(
                    sa.cast("id", sa.VARCHAR(4)), pr_parent.id,
                    sa.cast("name", sa.VARCHAR(4)), sa.func.coalesce(parent_res_tr.name, ""),
                    sa.cast("key", sa.VARCHAR(4)), pr_parent.key,
                    sa.cast("code", sa.VARCHAR(4)), pr_parent.code,
                    sa.cast("icon", sa.VARCHAR(4)), pr_parent.icon,
                ).label("parent")
            )
            .select_from(AuthResource)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = (
                query.outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(pr_parent, AuthResource.pid == pr_parent.id)
                .outerjoin(
                    parent_res_tr,
                    sa.and_(
                        parent_res_tr.resource_id == pr_parent.id,
                        parent_res_tr.locale_id == loc_id,
                    ),
                )
            )
        else:
            query = (
                query.outerjoin(AuthResourceTranslation, sa.false())
                .outerjoin(pr_parent, AuthResource.pid == pr_parent.id)
                .outerjoin(parent_res_tr, sa.false())
            )

        resource: AdminResourceDetail = await (
            query.where(AuthResource.id == resource_id).fetchrow(as_model=AdminResourceDetail)
        )
        if not resource:
            raise NotFoundException(detail=f"Resource {resource_id} not found")
        return resource

    async def create_resource(self, model: AdminResourceCreate) -> UUIDBaseModel:
        """
        Create a resource
        TODO: Log action
        :param model:
        :return:
        """
        rid = uuid.uuid4()
        try:
            await (
                self._session.insert(AuthResource)
                .values(
                    id=rid,
                    pid=model.pid,
                    key=model.key,
                    code=model.code,
                    icon=model.icon,
                    path=model.path,
                    type=model.type,
                    is_visible=model.is_visible,
                )
                .execute()
            )
            translation_payloads = model.translations or []
            if not translation_payloads and model.name and self._req_ctx and self._req_ctx.resolved_locale_id:
                translation_payloads = [
                    {
                        "locale_id": self._req_ctx.resolved_locale_id,
                        "name": model.name,
                        "description": model.description,
                        "remark": model.remark,
                    }
                ]

            if translation_payloads:
                locale_ids = [item.locale_id if hasattr(item, "locale_id") else item["locale_id"] for item in translation_payloads]
                active_locale_ids = set(await (
                    self._session.select(SystemLocale.id)
                    .where(SystemLocale.id.in_(locale_ids))
                    .where(SystemLocale.is_active == True)
                    .where(SystemLocale.is_deleted == False)
                    .fetchvals()
                ))
                if len(active_locale_ids) != len(set(locale_ids)):
                    raise ApiBaseException(
                        status_code=422,
                        detail="Invalid or inactive locale_id in translations",
                    )

                rows = [
                    dict(
                        resource_id=rid,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthResourceTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["resource_id", "locale_id"],
                        set_=dict(
                            name=sa.literal_column("excluded.name"),
                            description=sa.literal_column("excluded.description"),
                            remark=sa.literal_column("excluded.remark"),
                        ),
                    )
                    .execute()
                )
        except UniqueViolationError as e:
            raise ConflictErrorException(
                detail=f"Resource {model.code} already exists",
                debug_detail=str(e),
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            self._log_handler.create_log(
                OperationType.CREATE,
                record_id=rid,
                operation_code=AuthResource.__tablename__,
                new_data={
                    **model.model_dump(mode="json", exclude_none=True),
                    "id": str(rid),
                },
            )
            return UUIDBaseModel(id=rid)

    async def change_parent(self, resource_id: uuid.UUID, model: AdminResourceChangeParent):
        """

        :param resource_id:
        :param model:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            await (
                self._session.update(AuthResource)
                .values(pid=model.pid)
                .where(AuthResource.id == resource_id)
                .execute()
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_row = await self._get_resource_audit_dict(resource_id)
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=resource_id,
                operation_code=AuthResource.__tablename__,
                old_data=old_row,
                new_data=new_row,
            )

    async def update_resource(self, resource_id: uuid.UUID, model: AdminResourceUpdate):
        """
        Update a resource
        TODO: Log action
        :param resource_id:
        :param model:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            result = await (
                self._session.update(AuthResource)
                .values(
                    pid=model.pid,
                    key=model.key,
                    code=model.code,
                    icon=model.icon,
                    path=model.path,
                    type=model.type,
                    is_visible=model.is_visible,
                )
                .where(AuthResource.id == resource_id)
                .execute()
            )
            n = affected_rows(result)
            if n == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Resource {resource_id} not found",
                )
            translation_payloads = model.translations or []
            if not translation_payloads and model.name and self._req_ctx and self._req_ctx.resolved_locale_id:
                translation_payloads = [
                    {
                        "locale_id": self._req_ctx.resolved_locale_id,
                        "name": model.name,
                        "description": model.description,
                        "remark": model.remark,
                    }
                ]

            if translation_payloads:
                locale_ids = [item.locale_id if hasattr(item, "locale_id") else item["locale_id"] for item in translation_payloads]
                active_locale_ids = set(await (
                    self._session.select(SystemLocale.id)
                    .where(SystemLocale.id.in_(locale_ids))
                    .where(SystemLocale.is_active == True)
                    .where(SystemLocale.is_deleted == False)
                    .fetchvals()
                ))
                if len(active_locale_ids) != len(set(locale_ids)):
                    raise ApiBaseException(
                        status_code=422,
                        detail="Invalid or inactive locale_id in translations",
                    )

                rows = [
                    dict(
                        resource_id=resource_id,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthResourceTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["resource_id", "locale_id"],
                        set_=dict(
                            name=sa.literal_column("excluded.name"),
                            description=sa.literal_column("excluded.description"),
                            remark=sa.literal_column("excluded.remark"),
                        ),
                    )
                    .execute()
                )
        except UniqueViolationError as e:
            raise ConflictErrorException(
                detail=f"Resource {model.code} already exists",
                debug_detail=str(e),
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_row = await self._get_resource_audit_dict(resource_id)
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=resource_id,
                operation_code=AuthResource.__tablename__,
                old_data=old_row,
                new_data=new_row,
            )

    async def change_sequence(self, model: AdminResourceChangeSequence):
        """

        :param model:
        :return:
        """
        old_row = await self._get_resource_audit_dict(model.id)
        old_another_row = await self._get_resource_audit_dict(model.another_id)
        try:
            await (
                self._session.update(AuthResource)
                .values(sequence=model.another_sequence)
                .where(AuthResource.id == model.id)
                .execute()
            )
            await (
                self._session.update(AuthResource)
                .values(sequence=model.sequence)
                .where(AuthResource.id == model.another_id)
                .execute()
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_row = await self._get_resource_audit_dict(model.id)
            new_another_row = await self._get_resource_audit_dict(model.another_id)
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=model.id,
                operation_code=AuthResource.__tablename__,
                old_data=old_row,
                new_data=new_row,
            )
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=model.another_id,
                operation_code=AuthResource.__tablename__,
                old_data=old_another_row,
                new_data=new_another_row,
            )

    async def delete_resource(self, resource_id: uuid.UUID, model: DeleteBaseModel):
        """
        Delete a resource or soft delete. If permanent is True, then delete permanently.
        If resource_id is a parent resource, then all its children will be deleted as well.
        TODO: Log action
        :param resource_id:
        :param model:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            if not model.permanent:
                await (
                    self._session.update(AuthResource)
                    .values(is_deleted=True, delete_reason=model.reason)
                    .where(sa.or_(AuthResource.id == resource_id, AuthResource.pid == resource_id))
                    .execute()
                )
            else:
                await self._session.delete(AuthResource).where(AuthResource.id == resource_id).execute()
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            if model.permanent:
                self._log_handler.create_log(
                    OperationType.DELETE,
                    record_id=resource_id,
                    operation_code=AuthResource.__tablename__,
                    old_data=old_row,
                    new_data={"deleted": True, "permanent": True},
                )
            else:
                new_row = await self._get_resource_audit_dict(resource_id)
                self._log_handler.create_log(
                    OperationType.RECYCLE,
                    record_id=resource_id,
                    operation_code=AuthResource.__tablename__,
                    old_data=old_row,
                    new_data=new_row,
                )

    async def restore_resource(self, resource_id: uuid.UUID):
        """
        Restore the resource by setting is_deleted to False and deleted_reason to None.
        If resource_id is a parent resource, then all its children will be restored as well.
        TODO: Log action
        :param resource_id:
        :return:
        """
        old_row = await self._get_resource_audit_dict(resource_id)
        try:
            await (
                self._session.update(AuthResource)
                .values(is_deleted=False, delete_reason=None)
                .where(sa.or_(AuthResource.id == resource_id, AuthResource.pid == resource_id))
                .execute()
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_row = await self._get_resource_audit_dict(resource_id)
            self._log_handler.create_log(
                OperationType.RESTORE,
                record_id=resource_id,
                operation_code=AuthResource.__tablename__,
                old_data=old_row,
                new_data=new_row,
            )

    @staticmethod
    def build_tree(items: list[AdminResourceItem]) -> list[AdminResourceTreeItem]:
        """
        Build a tree from flat resource items using id/pid relations.
        Returns a list of root nodes, each with recursive children.
        :param items:
        :return:
        """
        nodes = {item.id: AdminResourceTreeItem(**item.model_dump()) for item in items}
        root_items: list[AdminResourceTreeItem] = []
        for node in nodes.values():
            if node.pid and node.pid in nodes:
                if not nodes[node.pid].children:
                    nodes[node.pid].children = []
                nodes[node.pid].children.append(node)
            else:
                root_items.append(node)

        def sort_nodes(arr: list[AdminResourceTreeItem]) -> None:
            arr.sort(key=lambda n: (n.sequence, n.name))
            for n in arr:
                if n.children:
                    sort_nodes(n.children)

        sort_nodes(root_items)
        return root_items

    async def get_admin_resource_tree(self) -> AdminResourceTree:
        """

        :return:
        """
        if not self._user_ctx.user_id or (not self._user_ctx.is_superuser and not self._user_ctx.is_admin):
            raise UnauthorizedException()

        resources: list[AdminResourceItem] = await self.get_resource_menus()
        hierarchical_items = self.build_tree(resources)
        return AdminResourceTree(items=hierarchical_items)

    async def get_resource_menus(self, is_deleted: bool = False) -> list[AdminResourceItem]:
        """

        :param is_deleted:
        :return:
        """
        query = (
            self._session.select(
                AuthResource.id,
                AuthResource.pid,
                sa.func.coalesce(AuthResourceTranslation.name, "").label("name"),
                AuthResource.key,
                AuthResource.code,
                AuthResource.icon,
                AuthResource.path,
                AuthResource.type,
                AuthResourceTranslation.description,
                AuthResourceTranslation.remark,
                AuthResource.sequence,
                AuthResource.is_deleted
            )
            .select_from(AuthResource)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = query.outerjoin(
                AuthResourceTranslation,
                sa.and_(
                    AuthResourceTranslation.resource_id == AuthResource.id,
                    AuthResourceTranslation.locale_id == loc_id,
                ),
            )
        else:
            query = query.outerjoin(AuthResourceTranslation, sa.false())

        resources: list[AdminResourceItem] = await (
            query.where(
                is_deleted == True, lambda: sa.or_(
                    AuthResource.is_deleted == is_deleted,
                    sa.and_(AuthResource.pid.is_(None), AuthResource.is_deleted == False)
                )
            )
            .where(is_deleted == False, lambda: AuthResource.is_deleted == is_deleted)
            .order_by(AuthResource.sequence)
            .fetch(as_model=AdminResourceItem)
        )
        return resources

    async def get_resource_by_user_id(self, user_id: uuid.UUID) -> list[AdminResourceItem]:
        """

        :param user_id:
        :return:
        """
        user_resources_subquery = (
            self._session.select(
                AuthResource.id.label("resource_id"),
                AuthResource.pid.label("parent_id")
            )
            .select_from(AuthUser)
            .join(AuthUser.roles)
            .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
            .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .where(AuthUser.id == user_id)
            .where(AuthResource.is_deleted == False)
            .where(AuthResource.is_visible == True)
            .where(AuthPermission.is_active == True)
            .where(AuthPermission.is_deleted == False)
            .where(AuthRole.is_active == True)
            .where(AuthRole.is_deleted == False)
            .where(sa.or_(AuthRolePermission.expire_date.is_(None), AuthRolePermission.expire_date > sa.func.now()))
            .subquery()
        )

        # 查询资源：资源 ID 在子查询中，或者资源 ID 是子查询中某个资源的父 ID
        query = (
            self._session.select(
                AuthResource.id,
                AuthResource.pid,
                sa.func.coalesce(AuthResourceTranslation.name, "").label("name"),
                AuthResource.key,
                AuthResource.code,
                AuthResource.icon,
                AuthResource.path,
                AuthResource.type,
                AuthResourceTranslation.description,
                AuthResourceTranslation.remark,
                AuthResource.sequence,
                AuthResource.is_deleted
            )
            .select_from(AuthResource)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = query.outerjoin(
                AuthResourceTranslation,
                sa.and_(
                    AuthResourceTranslation.resource_id == AuthResource.id,
                    AuthResourceTranslation.locale_id == loc_id,
                ),
            )
        else:
            query = query.outerjoin(AuthResourceTranslation, sa.false())

        resources: list[AdminResourceItem] = await (
            query.where(
                sa.or_(
                    AuthResource.id.in_(
                        sa.select(user_resources_subquery.c.resource_id)
                    ),
                    AuthResource.id.in_(
                        sa.select(user_resources_subquery.c.parent_id)
                        .where(user_resources_subquery.c.parent_id.isnot(None))
                    )
                )
            )
            .where(AuthResource.is_deleted == False)
            .distinct()
            .order_by(AuthResource.sequence)
            .fetch(as_model=AdminResourceItem)
        )
        return resources

    async def get_resources(self, model: DeleteQueryBaseModel):
        """
        get resources
        :param model:
        :return:
        """
        if not self._user_ctx.user_id or not self._user_ctx.is_admin:
            raise UnauthorizedException()
        resources = await self.get_resource_menus(is_deleted=model.deleted)
        return AdminResourceList(items=resources)

    async def get_user_permission_menus(self) -> AdminResourceList:
        """

        :return:
        """
        if not self._user_ctx.user_id or not self._user_ctx.is_admin:
            raise UnauthorizedException()

        if self._user_ctx.is_superuser:
            resource_items = await self.get_resource_menus()
        else:
            resource_items = await self.get_resource_by_user_id(user_id=self._user_ctx.user_id)

        await asyncio.sleep(1)
        return AdminResourceList(items=resource_items)
