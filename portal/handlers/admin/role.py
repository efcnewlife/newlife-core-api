"""
AdminRoleHandler
"""
import uuid
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from redis.asyncio import Redis
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from portal.config import settings
from portal.exceptions.responses import ConflictErrorException, ApiBaseException
from portal.handlers.admin.log import AdminLogHandler
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import get_request_context, RequestContext
from portal.libs.database import Session, RedisPool
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthRole,
    AuthUser,
    AuthPermission,
    AuthResource,
    AuthRolePermission,
    AuthRoleTranslation,
    AuthResourceTranslation,
    AuthPermissionTranslation,
    SystemLocale,
)
from portal.schemas.mixins import UUIDBaseModel
from portal.schemas.user import SUserSensitive
from portal.serializers.admin.v1.role import (
    AdminRolePages,
    AdminRoleTableItem,
    AdminRoleCreate,
    AdminRoleUpdate,
    AdminRolePermissionAssign,
    AdminRoleBase,
    AdminRoleList,
)
from portal.serializers.mixins import GenericQueryBaseModel, DeleteBaseModel


class AdminRoleHandler:
    """AdminRoleHandler"""

    def __init__(
        self,
        session: Session,
        redis_client: RedisPool,
        log_handler: AdminLogHandler,
    ):
        self._session = session
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._log_handler = log_handler
        self._req_ctx: Optional[RequestContext] = get_request_context()

    @staticmethod
    def user_role_key(user_id: UUID) -> str:
        """
        Get user role cache key
        :param user_id:
        :return:
        """
        return CacheKeys("role").add_attribute(str(user_id)).build()

    async def _get_role_audit_dict(self, role_id: UUID) -> Optional[dict[str, Any]]:
        role = await self.get_role_by_id(role_id)
        if not role:
            return None
        return role.model_dump(mode="json")

    async def init_user_roles_cache(self, user: SUserSensitive, expire: int) -> Optional[list[str]]:
        """
        Initialize user roles cache
        :param user:
        :param expire:
        :return:
        """
        await self.clear_user_roles_cache(user_id=user.id)
        role_codes = await self._session.select(AuthRole.code) \
            .join(AuthRole.users) \
            .where(AuthUser.id == user.id) \
            .where(AuthRole.is_deleted == False) \
            .where(AuthUser.is_deleted == False) \
            .order_by(AuthRole.code) \
            .fetchvals()
        if user.is_superuser:
            role_codes = ["superadmin"]
        if not role_codes:
            return None
        key = self.user_role_key(user.id)
        await self._redis.sadd(key, *role_codes)
        await self._redis.expire(key, expire)
        return role_codes

    async def clear_user_roles_cache(self, user_id: UUID):
        """
        Clear user roles cache
        :param user_id:
        :return:
        """
        key = self.user_role_key(user_id)
        await self._redis.delete(key)

    async def get_role_pages(self, model: GenericQueryBaseModel) -> AdminRolePages:
        """

        :param model:
        :return:
        """
        permissions_jsonb = sa.cast(
            sa.func.json_build_object(
                sa.cast("id", sa.VARCHAR(4)), AuthPermission.id,
                sa.cast("resource_name", sa.VARCHAR(16)), sa.func.coalesce(AuthResourceTranslation.name, ""),
                sa.cast("name", sa.VARCHAR(16)), sa.func.coalesce(AuthPermissionTranslation.name, ""),
                sa.cast("code", sa.VARCHAR(4)), AuthPermission.code,
            ),
            JSONB,
        )
        agg_permissions = sa.func.array_agg(
            sa.distinct(permissions_jsonb)
        ).filter(AuthPermission.id.isnot(None))

        permissions_coalesced = sa.func.coalesce(
            agg_permissions,
            sa.cast(sa.text("'{}'"), ARRAY(JSONB))
        ).label("permissions")

        query = (
            self._session.select(
                AuthRole.id,
                AuthRole.code,
                sa.func.max(AuthRoleTranslation.name).label("name"),
                AuthRole.is_active,
                AuthRole.created_at,
                AuthRole.created_by,
                AuthRole.updated_at,
                AuthRole.updated_by,
                AuthRole.delete_reason,
                sa.func.max(AuthRoleTranslation.description).label("description"),
                sa.func.max(AuthRoleTranslation.remark).label("remark"),
                permissions_coalesced
            )
            .select_from(AuthRole)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = (
                query.outerjoin(
                    AuthRoleTranslation,
                    sa.and_(
                        AuthRoleTranslation.role_id == AuthRole.id,
                        AuthRoleTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
                .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == loc_id,
                    ),
                )
            )
        else:
            query = (
                query.outerjoin(AuthRoleTranslation, sa.false())
                .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
                .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(AuthResourceTranslation, sa.false())
                .outerjoin(AuthPermissionTranslation, sa.false())
            )

        items, count = await (
            query.where(AuthRole.is_deleted == model.deleted)
            .where(
                model.keyword, lambda: sa.or_(
                    AuthRoleTranslation.name.ilike(f"%{model.keyword}%"),
                    AuthRole.code.ilike(f"%{model.keyword}%")
                )
            )
            .group_by(AuthRole.id)
            .order_by_with(
                tables=[AuthRole],
                order_by=model.order_by,
                descending=model.descending
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(
                no_order_by=False,
                as_model=AdminRoleTableItem
            )
        )  # type: (list[AdminRoleTableItem], int)

        return AdminRolePages(
            page=model.page,
            page_size=model.page_size,
            total=count,
            items=items
        )

    async def get_active_roles(self) -> AdminRoleList:
        """

        :return:
        """
        query = (
            self._session.select(
                AuthRole.id,
                AuthRole.code,
                sa.func.max(AuthRoleTranslation.name).label("name"),
            )
            .select_from(AuthRole)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = query.outerjoin(
                AuthRoleTranslation,
                sa.and_(
                    AuthRoleTranslation.role_id == AuthRole.id,
                    AuthRoleTranslation.locale_id == loc_id,
                ),
            )
        else:
            query = query.outerjoin(AuthRoleTranslation, sa.false())

        roles: list[AdminRoleBase] = await (
            query.where(AuthRole.is_active == True)
            .group_by(AuthRole.id)
            .fetch(as_model=AdminRoleBase)
        )
        if not roles:
            return AdminRoleList(items=[])
        return AdminRoleList(items=roles)

    async def get_role_by_id(self, role_id: UUID) -> Optional[AdminRoleTableItem]:
        """

        :param role_id:
        :return:
        """
        permissions_jsonb = sa.cast(
            sa.func.json_build_object(
                sa.cast("id", sa.VARCHAR(4)), AuthPermission.id,
                sa.cast("resource_name", sa.VARCHAR(16)), sa.func.coalesce(AuthResourceTranslation.name, ""),
                sa.cast("name", sa.VARCHAR(16)), sa.func.coalesce(AuthPermissionTranslation.name, ""),
                sa.cast("code", sa.VARCHAR(4)), AuthPermission.code,
            ),
            JSONB,
        )
        agg_permissions = sa.func.array_agg(
            sa.distinct(permissions_jsonb)
        ).filter(AuthPermission.id.isnot(None))

        permissions_coalesced = sa.func.coalesce(
            agg_permissions,
            sa.cast(sa.text("'{}'"), ARRAY(JSONB))
        ).label("permissions")
        query = (
            self._session.select(
                AuthRole.id,
                AuthRole.code,
                sa.func.max(AuthRoleTranslation.name).label("name"),
                AuthRole.is_active,
                AuthRole.created_at,
                AuthRole.created_by,
                AuthRole.updated_at,
                AuthRole.updated_by,
                AuthRole.delete_reason,
                sa.func.max(AuthRoleTranslation.description).label("description"),
                sa.func.max(AuthRoleTranslation.remark).label("remark"),
                permissions_coalesced
            )
            .select_from(AuthRole)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = (
                query.outerjoin(
                    AuthRoleTranslation,
                    sa.and_(
                        AuthRoleTranslation.role_id == AuthRole.id,
                        AuthRoleTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
                .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == loc_id,
                    ),
                )
            )
        else:
            query = (
                query.outerjoin(AuthRoleTranslation, sa.false())
                .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
                .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(AuthResourceTranslation, sa.false())
                .outerjoin(AuthPermissionTranslation, sa.false())
            )

        role: Optional[AdminRoleTableItem] = await (
            query.where(AuthRole.id == role_id)
            .group_by(AuthRole.id)
            .fetchrow(as_model=AdminRoleTableItem)
        )
        if not role:
            return None
        return role

    async def create_role(self, model: AdminRoleCreate) -> UUIDBaseModel:
        """

        :param model:
        :return:
        """
        role_id = uuid.uuid4()
        try:
            await (
                self._session.insert(AuthRole)
                .values(
                    code=model.code,
                    is_active=model.is_active,
                    id=role_id,
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
                        role_id=role_id,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthRoleTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["role_id", "locale_id"],
                        set_=dict(
                            name=sa.literal_column("excluded.name"),
                            description=sa.literal_column("excluded.description"),
                            remark=sa.literal_column("excluded.remark"),
                        ),
                    )
                    .execute()
                )
            await (
                self._session.insert(AuthRolePermission)
                .values(
                    [
                        {"role_id": role_id.hex, "permission_id": permission_id.hex}
                        for permission_id in model.permissions
                    ]
                )
                .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
                .execute()
            )
        except UniqueViolationError as e:
            raise ConflictErrorException(
                detail="Role code already exists",
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
                record_id=role_id,
                operation_code=AuthRole.__tablename__,
                new_data={
                    **model.model_dump(mode="json", exclude_none=True, exclude={"permissions"}),
                    "id": str(role_id),
                },
            )
            self._log_handler.create_log(
                OperationType.CREATE,
                record_id=role_id,
                operation_code=AuthRolePermission.__tablename__,
                new_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in model.permissions],
                },
            )
            return UUIDBaseModel(id=role_id)

    async def update_role(self, role_id: UUID, model: AdminRoleUpdate) -> None:
        """

        :param role_id:
        :param model:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        old_permission_ids = await (
            self._session.select(AuthRolePermission.permission_id)
            .where(AuthRolePermission.role_id == role_id)
            .fetchvals()
        )
        try:
            result = await (
                self._session.insert(AuthRole)
                .values(
                    code=model.code,
                    is_active=model.is_active,
                    id=role_id,
                )
                .on_conflict_do_update(
                    index_elements=[AuthRole.id],
                    set_=dict(
                        code=model.code,
                        is_active=model.is_active,
                    ),
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
                        role_id=role_id,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthRoleTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["role_id", "locale_id"],
                        set_=dict(
                            name=sa.literal_column("excluded.name"),
                            description=sa.literal_column("excluded.description"),
                            remark=sa.literal_column("excluded.remark"),
                        ),
                    )
                    .execute()
                )

            # Determine which permissions to add and which to delete by set difference
            new_permission_ids = set(model.permissions or [])
            old_permission_id_set = set(old_permission_ids)
            insert_permission_ids = list(new_permission_ids - old_permission_id_set)
            delete_permission_ids = list(old_permission_id_set - new_permission_ids)

            if insert_permission_ids:
                await (
                    self._session.insert(AuthRolePermission)
                    .values(
                        [
                            {"role_id": role_id.hex, "permission_id": permission_id.hex}
                            for permission_id in insert_permission_ids
                        ]
                    )
                    .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
                    .execute()
                )

            if delete_permission_ids:
                await (
                    self._session.delete(AuthRolePermission)
                    .where(AuthRolePermission.role_id == role_id)
                    .where(AuthRolePermission.permission_id.in_(delete_permission_ids))
                    .execute()
                )

            if affected_rows(result) == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Role {role_id} not found",
                )
        except UniqueViolationError as e:
            raise ConflictErrorException(
                detail="Role code already exists",
                debug_detail=str(e),
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_role_row = await self._get_role_audit_dict(role_id)
            if old_role_row is not None and new_role_row is not None:
                self._log_handler.create_log(
                    OperationType.UPDATE,
                    record_id=role_id,
                    operation_code=AuthRole.__tablename__,
                    old_data=old_role_row,
                    new_data=new_role_row,
                )
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=role_id,
                operation_code=AuthRolePermission.__tablename__,
                old_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in old_permission_ids],
                },
                new_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in model.permissions or []],
                },
            )

    async def delete_role(self, role_id: UUID, model: DeleteBaseModel) -> None:
        """

        :param model:
        :param role_id:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        old_permission_ids = await (
            self._session.select(AuthRolePermission.permission_id)
            .where(AuthRolePermission.role_id == role_id)
            .fetchvals()
        )
        try:
            if not model.permanent:
                await (
                    self._session.update(AuthRole)
                    .values(is_deleted=True, delete_reason=model.reason)
                    .where(AuthRole.id == role_id)
                    .execute()
                )
            else:
                await (
                    self._session.delete(AuthRolePermission)
                    .where(AuthRolePermission.role_id == role_id)
                    .execute()
                )
                await (
                    self._session.delete(AuthRole)
                    .where(AuthRole.id == role_id)
                    .execute()
                )

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
                    record_id=role_id,
                    operation_code=AuthRole.__tablename__,
                    old_data=old_role_row,
                    new_data={"deleted": True, "permanent": True},
                )
                self._log_handler.create_log(
                    OperationType.DELETE,
                    record_id=role_id,
                    operation_code=AuthRolePermission.__tablename__,
                    old_data={
                        "role_id": str(role_id),
                        "permission_ids": [str(item) for item in old_permission_ids],
                    },
                    new_data={"role_id": str(role_id), "permission_ids": []},
                )
            else:
                base = dict(old_role_row) if old_role_row else {"id": str(role_id)}
                self._log_handler.create_log(
                    OperationType.RECYCLE,
                    record_id=role_id,
                    operation_code=AuthRole.__tablename__,
                    old_data=old_role_row,
                    new_data={
                        **base,
                        "is_deleted": True,
                        "delete_reason": model.reason,
                    },
                )

    async def restore_role(self, role_id: UUID) -> None:
        """

        :param role_id:
        :return:
        """
        old_role_row = await self._get_role_audit_dict(role_id)
        try:
            await (
                self._session.update(AuthRole)
                .values(is_deleted=False, delete_reason=None)
                .where(AuthRole.id == role_id)
                .execute()
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_role_row = await self._get_role_audit_dict(role_id)
            self._log_handler.create_log(
                OperationType.RESTORE,
                record_id=role_id,
                operation_code=AuthRole.__tablename__,
                old_data=old_role_row,
                new_data=new_role_row,
            )

    async def assign_role_permissions(self, role_id: UUID, model: AdminRolePermissionAssign) -> None:
        """

        :param role_id:
        :param model:
        :return:
        """
        original_permissions = await (
            self._session.select(AuthRolePermission.permission_id)
            .where(AuthRolePermission.role_id == role_id)
            .fetchvals()
        )
        insert_permissions = [
            {
                "role_id": role_id,
                "permission_id": permission_id
            } for permission_id in model.permission_ids if permission_id not in original_permissions
        ]
        delete_permissions = [
            permission_id for permission_id in original_permissions if permission_id not in model.permission_ids
        ]
        try:
            await (
                self._session.insert(AuthRolePermission)
                .values(insert_permissions)
                .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
                .execute()
            )
            await (
                self._session.delete(AuthRolePermission)
                .where(AuthRolePermission.role_id == role_id)
                .where(AuthRolePermission.permission_id.in_(delete_permissions))
                .execute()
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            self._log_handler.create_log(
                OperationType.UPDATE,
                record_id=role_id,
                operation_code=AuthRolePermission.__tablename__,
                old_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in original_permissions],
                },
                new_data={
                    "role_id": str(role_id),
                    "permission_ids": [str(item) for item in model.permission_ids],
                },
            )
