"""
AdminPermissionHandler
"""
import uuid
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from redis.asyncio import Redis

from portal.config import settings
from portal.exceptions.responses import ApiBaseException, ConflictErrorException
from portal.handlers.admin.log import AdminLogHandler
from portal.libs.contexts.request_context import get_request_context, RequestContext
from portal.libs.consts.enums import OperationType
from portal.libs.consts.cache_keys import CacheKeys, CacheExpiry
from portal.libs.database import Session, RedisPool
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthPermission,
    AuthPermissionTranslation,
    AuthVerb,
    AuthVerbTranslation,
    AuthResource,
    AuthResourceTranslation,
    AuthRole,
    AuthUser,
    AuthRolePermission,
    SystemLocale,
)
from portal.schemas.mixins import UUIDBaseModel
from portal.schemas.permission import PermissionBase
from portal.schemas.user import SUserSensitive
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.admin.v1.permission import (
    AdminPermissionDetail,
    AdminPermissionCreate,
    AdminPermissionUpdate,
    AdminPermissionQuery,
    AdminPermissionPageItem,
    AdminPermissionPage,
    AdminPermissionBulkAction,
    AdminPermissionList,
    AdminPermissionItem,
)


class AdminPermissionHandler:
    """AdminPermissionHandler"""

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
    def permission_key(user_id: UUID, permission_code: Optional[str] = None) -> str:
        """
        Generate Redis key for user permissions
        :param user_id:
        :param permission_code:
        :return:
        """
        if permission_code:
            return CacheKeys(resource="permission").add_attribute(str(user_id)).add_attribute(permission_code).build()
        return CacheKeys(resource="permission").add_attribute(str(user_id)).build()

    async def _get_permission_audit_dict(self, permission_id: UUID) -> Optional[dict[str, Any]]:
        permission = await self.get_permission_by_id(permission_id)
        if not permission:
            return None
        return permission.model_dump(mode="json")

    async def init_user_permissions_cache(self, user: SUserSensitive, expire: int) -> Optional[list[str]]:
        """
        Initialize user permissions cache
        :param user:
        :param expire:
        :return:
        """
        await self.clear_user_permissions_cache(user_id=user.id)
        permissions: Optional[list[PermissionBase]] = await self._get_user_role_permissions(user=user)
        if not permissions:
            return None
        key = self.permission_key(user_id=user.id)
        permission_codes = []
        for permission in permissions:
            permission_code = permission.code
            permission_codes.append(permission_code)
            await self._redis.hset(key, permission_code, permission.model_dump_json())
        await self._redis.expire(key, expire)
        return permission_codes

    async def clear_user_permissions_cache(self, user_id: UUID):
        """
        Clear user permissions cache
        :param user_id:
        :return:
        """
        key = self.permission_key(user_id=user_id)
        await self._redis.delete(key)

    async def _get_user_role_permissions(self, user: SUserSensitive) -> Optional[list[PermissionBase]]:
        """
        Get permissions by user role
        :param user:
        :return:
        """
        if user.is_superuser:
            return await self._get_all_permissions()
        return await (
            self._session.select(
                AuthPermission.code,
                AuthVerb.action,
                AuthResource.code.label("resource_code")
            )
            .select_from(AuthUser)
            .join(AuthUser.roles)
            .join(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
            .join(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
            .join(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .join(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .where(AuthUser.id == user.id)
            .where(AuthUser.is_deleted == False)
            .where(AuthUser.is_active == True)
            .where(AuthUser.verified == True)
            .where(AuthRole.is_deleted == False)
            .where(AuthRole.is_active == True)
            .where(AuthPermission.is_deleted == False)
            .where(AuthPermission.is_active == True)
            .where(AuthVerb.is_deleted == False)
            .where(AuthVerb.is_active == True)
            .where(AuthResource.is_deleted == False)
            .where(AuthResource.is_visible == True)
            .where(
                sa.or_(
                    AuthRolePermission.expire_date.is_(None),
                    AuthRolePermission.expire_date > sa.func.now()
                )
            )
            .distinct()
            .order_by(
                [
                    AuthResource.code,
                    AuthVerb.action,
                    AuthPermission.code,
                ]
            )
            .fetch(as_model=PermissionBase)
        )

    async def _get_all_permissions(self) -> Optional[list[PermissionBase]]:
        """
        Get all permissions
        :return:
        """
        return await (
            self._session.select(
                AuthPermission.code,
                AuthVerb.action,
                AuthResource.code.label("resource_code")
            )
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .where(AuthPermission.is_active == True)
            .fetch(as_model=PermissionBase)
        )

    async def get_permission_by_id(self, permission_id: UUID) -> Optional[AdminPermissionDetail]:
        """
        Get permission by id
        :param permission_id:
        :return:
        """
        query = (
            self._session.select(
                AuthPermission.id,
                sa.func.coalesce(AuthPermissionTranslation.name, "").label("name"),
                AuthPermission.code,
                sa.func.json_build_object(
                    sa.cast("id", sa.VARCHAR(4)), AuthResource.id,
                    sa.cast("name", sa.VARCHAR(4)), sa.func.coalesce(AuthResourceTranslation.name, ""),
                    sa.cast("key", sa.VARCHAR(4)), AuthResource.key,
                    sa.cast("code", sa.VARCHAR(4)), AuthResource.code
                ).label("resource"),
                sa.func.json_build_object(
                    sa.cast("id", sa.VARCHAR(4)), AuthVerb.id,
                    sa.cast("name", sa.VARCHAR(4)), sa.func.coalesce(AuthVerbTranslation.name, ""),
                    sa.cast("action", sa.VARCHAR(8)), AuthVerb.action
                ).label("verb"),
                AuthPermission.is_active,
                AuthPermissionTranslation.description,
                AuthPermissionTranslation.remark
            )
            .select_from(AuthPermission)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = (
                query.outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(
                    AuthVerbTranslation,
                    sa.and_(
                        AuthVerbTranslation.verb_id == AuthVerb.id,
                        AuthVerbTranslation.locale_id == loc_id,
                    ),
                )
            )
        else:
            query = (
                query.outerjoin(AuthPermissionTranslation, sa.false())
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(AuthResourceTranslation, sa.false())
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(AuthVerbTranslation, sa.false())
            )

        try:
            item: Optional[AdminPermissionDetail] = await (
                query.where(AuthPermission.id == permission_id).fetchrow(as_model=AdminPermissionDetail)
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            return item

    async def get_permission_pages(
        self,
        model: AdminPermissionQuery
    ):
        """

        :param model:
        :return:
        """
        query = (
            self._session.select(
                AuthPermission.id,
                sa.func.coalesce(AuthPermissionTranslation.name, "").label("name"),
                AuthPermission.code,
                AuthPermission.is_active,
                AuthPermissionTranslation.description,
                AuthPermissionTranslation.remark,
                sa.func.coalesce(AuthResourceTranslation.name, "").label("resource_name"),
                sa.func.coalesce(AuthVerbTranslation.name, "").label("verb_name"),
            )
            .select_from(AuthPermission)
        )
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            loc_id = self._req_ctx.resolved_locale_id
            query = (
                query.outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == loc_id,
                    ),
                )
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(
                    AuthVerbTranslation,
                    sa.and_(
                        AuthVerbTranslation.verb_id == AuthVerb.id,
                        AuthVerbTranslation.locale_id == loc_id,
                    ),
                )
            )
        else:
            query = (
                query.outerjoin(AuthPermissionTranslation, sa.false())
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(AuthResourceTranslation, sa.false())
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(AuthVerbTranslation, sa.false())
            )

        items, count = await (
            query.where(AuthPermission.is_deleted == model.deleted)
            .where(
                model.keyword, lambda: sa.or_(
                    AuthPermissionTranslation.name.ilike(f"%{model.keyword}%"),
                    AuthPermission.code.ilike(f"%{model.keyword}%")
                )
            )
            .where(model.is_active is not None, lambda: AuthPermission.is_active == model.is_active)
            .order_by_with(
                tables=[AuthPermission],
                order_by=model.order_by,
                descending=model.descending
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(as_model=AdminPermissionPageItem)
        )  # type: (list[AdminPermissionPageItem], int)
        return AdminPermissionPage(
            page=model.page,
            page_size=model.page_size,
            total=count,
            items=items
        )

    async def create_permission(self, model: AdminPermissionCreate) -> UUIDBaseModel:
        """
        Create a permission
        :param model:
        :return:
        """
        permission_id = uuid.uuid4()
        try:
            main_payload = {
                "id": permission_id,
                "code": model.code,
                "resource_id": model.resource_id,
                "verb_id": model.verb_id,
                "is_active": model.is_active,
            }
            await (
                self._session.insert(AuthPermission)
                .values(main_payload)
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
                        permission_id=permission_id,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthPermissionTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["permission_id", "locale_id"],
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
                detail=f"Permission {model.code} already exists",
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
                record_id=permission_id,
                operation_code=AuthPermission.__tablename__,
                new_data={
                    **model.model_dump(mode="json", exclude_none=True),
                    "id": str(permission_id),
                },
            )
            return UUIDBaseModel(id=permission_id)

    async def update_permission(self, permission_id: UUID, model: AdminPermissionUpdate) -> None:
        """
        Update a permission
        :param permission_id:
        :param model:
        :return:
        """
        old_row = await self._get_permission_audit_dict(permission_id)
        try:
            result = await (
                self._session.update(AuthPermission)
                .values(
                    code=model.code,
                    resource_id=model.resource_id,
                    verb_id=model.verb_id,
                    is_active=model.is_active,
                )
                .where(AuthPermission.id == permission_id)
                .where(AuthPermission.is_deleted == False)
                .execute()
            )
            n = affected_rows(result)
            if n == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Permission {permission_id} not found",
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
                        permission_id=permission_id,
                        locale_id=item.locale_id if hasattr(item, "locale_id") else item["locale_id"],
                        name=item.name if hasattr(item, "name") else item["name"],
                        description=item.description if hasattr(item, "description") else item.get("description"),
                        remark=item.remark if hasattr(item, "remark") else item.get("remark"),
                    )
                    for item in translation_payloads
                ]
                await (
                    self._session.insert(AuthPermissionTranslation)
                    .values(rows)
                    .on_conflict_do_update(
                        index_elements=["permission_id", "locale_id"],
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
                detail=f"Permission {model.code} already exists",
                debug_detail=str(e),
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )
        else:
            new_row = await self._get_permission_audit_dict(permission_id)
            if old_row is not None and new_row is not None:
                self._log_handler.create_log(
                    OperationType.UPDATE,
                    record_id=permission_id,
                    operation_code=AuthPermission.__tablename__,
                    old_data=old_row,
                    new_data=new_row,
                )

    async def delete_permission(self, permission_id: UUID, model: DeleteBaseModel) -> None:
        """
        Delete a permission
        :param permission_id:
        :param model:
        :return:
        """
        old_row = await self._get_permission_audit_dict(permission_id)
        try:
            if model.permanent:
                # Hard delete - permanently remove from database
                result = await (
                    self._session.delete(AuthPermission)
                    .where(AuthPermission.id == permission_id)
                    .execute()
                )
            else:
                # Soft delete - mark as deleted with reason
                result = await (
                    self._session.update(AuthPermission)
                    .values(
                        is_deleted=True,
                        delete_reason=model.reason
                    )
                    .where(AuthPermission.id == permission_id)
                    .where(AuthPermission.is_deleted == False)
                    .execute()
                )

            if affected_rows(result) == 0:
                raise ApiBaseException(
                    status_code=404,
                    detail=f"Permission {permission_id} not found",
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
                    record_id=permission_id,
                    operation_code=AuthPermission.__tablename__,
                    old_data=old_row,
                    new_data={"deleted": True, "permanent": True},
                )
            else:
                base = dict(old_row) if old_row else {"id": str(permission_id)}
                self._log_handler.create_log(
                    OperationType.RECYCLE,
                    record_id=permission_id,
                    operation_code=AuthPermission.__tablename__,
                    old_data=old_row,
                    new_data={
                        **base,
                        "is_deleted": True,
                        "delete_reason": model.reason,
                    },
                )

    async def restore_permission(self, model: AdminPermissionBulkAction) -> None:
        """
        Restore a permission
        :param model:
        :return:
        """
        try:
            await (
                self._session.update(AuthPermission)
                .values(is_deleted=False, delete_reason=None)
                .where(AuthPermission.id.in_(model.ids))
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
                OperationType.RESTORE,
                operation_code=AuthPermission.__tablename__,
                old_data={"permission_ids": [str(item) for item in model.ids]},
                new_data={"is_deleted": False, "delete_reason": None},
            )

    async def get_permission_list(self):
        """

        :return:
        """
        if not (self._req_ctx and self._req_ctx.resolved_locale_id):
            return AdminPermissionList(items=[])
        loc_id = self._req_ctx.resolved_locale_id
        cache_key = (
            CacheKeys(resource="permission")
            .add_attribute("list")
            .add_attribute(str(loc_id))
            .build()
        )
        cached = await self._redis.get(cache_key)
        if cached:
            return AdminPermissionList.model_validate_json(cached)

        query = (
            self._session.select(
                AuthPermission.id,
                sa.func.coalesce(AuthPermissionTranslation.name, "").label("name"),
                AuthPermission.code,
                AuthPermission.is_active,
                AuthPermissionTranslation.description,
                AuthPermissionTranslation.remark,
                AuthPermission.resource_id,
                AuthPermission.verb_id,
            )
            .select_from(AuthPermission)
            .outerjoin(
                AuthPermissionTranslation,
                sa.and_(
                    AuthPermissionTranslation.permission_id == AuthPermission.id,
                    AuthPermissionTranslation.locale_id == loc_id,
                ),
            )
        )
        permissions: list[AdminPermissionItem] = await (
            query.where(AuthPermission.is_deleted == False)
            .order_by(AuthPermission.resource_id)
            .fetch(as_model=AdminPermissionItem)
        )
        result = AdminPermissionList(items=permissions)
        await self._redis.set(cache_key, result.model_dump_json(), ex=CacheExpiry.MONTH)
        return result
