"""
Permission repository implementation.
"""
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError

from portal.application.rbac.commands import PermissionPagesQueryCommand
from portal.domain.rbac.entities import (
    PermissionDetail,
    PermissionListItem,
    PermissionPageItem,
    PermissionRecord,
)
from portal.exceptions.responses import ApiBaseException
from portal.libs.database import Session
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


class PermissionRepository:
    """SQLAlchemy-backed permission repository."""

    def __init__(self, session: Session):
        self._session = session

    def _detail_query(self, locale_id: Optional[UUID]):
        query = (
            self._session.select(
                AuthPermission.id,
                sa.func.coalesce(AuthPermissionTranslation.name, "").label("name"),
                AuthPermission.code,
                sa.func.json_build_object(
                    sa.cast("id", sa.VARCHAR(4)), AuthResource.id,
                    sa.cast("name", sa.VARCHAR(4)), sa.func.coalesce(AuthResourceTranslation.name, ""),
                    sa.cast("key", sa.VARCHAR(4)), AuthResource.key,
                    sa.cast("code", sa.VARCHAR(4)), AuthResource.code,
                ).label("resource"),
                sa.func.json_build_object(
                    sa.cast("id", sa.VARCHAR(4)), AuthVerb.id,
                    sa.cast("name", sa.VARCHAR(4)), sa.func.coalesce(AuthVerbTranslation.name, ""),
                    sa.cast("action", sa.VARCHAR(8)), AuthVerb.action,
                ).label("verb"),
                AuthPermission.is_active,
                AuthPermission.resource_id,
                AuthPermission.verb_id,
                AuthPermissionTranslation.description,
                AuthPermissionTranslation.remark,
            )
            .select_from(AuthPermission)
        )
        if locale_id:
            return (
                query.outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(
                    AuthVerbTranslation,
                    sa.and_(
                        AuthVerbTranslation.verb_id == AuthVerb.id,
                        AuthVerbTranslation.locale_id == locale_id,
                    ),
                )
            )
        return (
            query.outerjoin(AuthPermissionTranslation, sa.false())
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .outerjoin(AuthResourceTranslation, sa.false())
            .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .outerjoin(AuthVerbTranslation, sa.false())
        )

    def _pages_query(self, locale_id: Optional[UUID]):
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
        if locale_id:
            return (
                query.outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
                .outerjoin(
                    AuthVerbTranslation,
                    sa.and_(
                        AuthVerbTranslation.verb_id == AuthVerb.id,
                        AuthVerbTranslation.locale_id == locale_id,
                    ),
                )
            )
        return (
            query.outerjoin(AuthPermissionTranslation, sa.false())
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .outerjoin(AuthResourceTranslation, sa.false())
            .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .outerjoin(AuthVerbTranslation, sa.false())
        )

    async def get_by_id(
        self,
        permission_id: UUID,
        locale_id: Optional[UUID],
    ) -> Optional[PermissionDetail]:
        """
        Fetch permission detail by id.
        :param permission_id:
        :param locale_id:
        :return:
        """
        try:
            return await (
                self._detail_query(locale_id)
                .where(AuthPermission.id == permission_id)
                .fetchrow(as_model=PermissionDetail)
            )
        except Exception as e:
            raise ApiBaseException(
                status_code=500,
                detail="Internal Server Error",
                debug_detail=str(e),
            )

    async def fetch_pages(
        self,
        command: PermissionPagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[PermissionPageItem], int]:
        """
        Paginated permission list.
        :param model:
        :param locale_id:
        :return:
        """
        items, count = await (
            self._pages_query(locale_id)
            .where(AuthPermission.is_deleted == command.deleted)
            .where(
                command.keyword,
                lambda: sa.or_(
                    AuthPermissionTranslation.name.ilike(f"%{command.keyword}%"),
                    AuthPermission.code.ilike(f"%{command.keyword}%"),
                ),
            )
            .where(command.is_active is not None, lambda: AuthPermission.is_active == command.is_active)
            .order_by_with(
                tables=[AuthPermission],
                order_by=command.order_by,
                descending=command.descending,
            )
            .limit(command.page_size)
            .offset(command.page * command.page_size)
            .fetchpages(as_model=PermissionPageItem)
        )
        return items, count

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        """
        Return active, non-deleted locale ids from the given set.
        :param locale_ids:
        :return:
        """
        active_locale_ids = await (
            self._session.select(SystemLocale.id)
            .where(SystemLocale.id.in_(locale_ids))
            .where(SystemLocale.is_active == True)
            .where(SystemLocale.is_deleted == False)
            .fetchvals()
        )
        return set(active_locale_ids)

    async def insert_permission(self, payload: dict[str, Any]) -> None:
        """
        Insert auth_permission row.
        :param payload:
        :return:
        """
        await (
            self._session.insert(AuthPermission)
            .values(payload)
            .execute()
        )

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        """
        Upsert permission translation rows.
        :param rows:
        :return:
        """
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

    async def update_permission(
        self,
        permission_id: UUID,
        values: dict[str, Any],
    ) -> int:
        """
        Update permission row; returns affected row count.
        :param permission_id:
        :param values:
        :return:
        """
        result = await (
            self._session.update(AuthPermission)
            .values(**values)
            .where(AuthPermission.id == permission_id)
            .where(AuthPermission.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_hard(self, permission_id: UUID) -> int:
        """
        Permanently delete permission.
        :param permission_id:
        :return:
        """
        result = await (
            self._session.delete(AuthPermission)
            .where(AuthPermission.id == permission_id)
            .execute()
        )
        return affected_rows(result)

    async def delete_soft(self, permission_id: UUID, reason: Optional[str]) -> int:
        """
        Soft-delete permission.
        :param permission_id:
        :param reason:
        :return:
        """
        result = await (
            self._session.update(AuthPermission)
            .values(is_deleted=True, delete_reason=reason)
            .where(AuthPermission.id == permission_id)
            .where(AuthPermission.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def restore_permissions(self, permission_ids: list[UUID]) -> None:
        """
        Restore soft-deleted permissions.
        :param permission_ids:
        :return:
        """
        await (
            self._session.update(AuthPermission)
            .values(is_deleted=False, delete_reason=None)
            .where(AuthPermission.id.in_(permission_ids))
            .execute()
        )

    async def list_for_locale(self, locale_id: UUID) -> list[PermissionListItem]:
        """
        List non-deleted permissions for admin list endpoint.
        :param locale_id:
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
                AuthPermission.resource_id,
                AuthPermission.verb_id,
            )
            .select_from(AuthPermission)
            .outerjoin(
                AuthPermissionTranslation,
                sa.and_(
                    AuthPermissionTranslation.permission_id == AuthPermission.id,
                    AuthPermissionTranslation.locale_id == locale_id,
                ),
            )
        )
        permissions: list[PermissionListItem] = await (
            query.where(AuthPermission.is_deleted == False)
            .order_by(AuthPermission.resource_id)
            .fetch(as_model=PermissionListItem)
        )
        return permissions or []

    async def list_user_role_permissions(self, user_id: UUID) -> list[PermissionRecord]:
        """
        Permissions granted via user roles.
        :param user_id:
        :return:
        """
        permissions: list[PermissionRecord] = await (
            self._session.select(
                AuthPermission.code,
                AuthVerb.action,
                AuthResource.code.label("resource_code"),
            )
            .select_from(AuthUser)
            .join(AuthUser.roles)
            .join(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
            .join(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
            .join(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .join(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .where(AuthUser.id == user_id)
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
                    AuthRolePermission.expire_date > sa.func.now(),
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
            .fetch(as_model=PermissionRecord)
        )
        return permissions or []

    async def list_all_permissions(self) -> list[PermissionRecord]:
        """
        All active permissions (superuser).
        :return:
        """
        permissions: list[PermissionRecord] = await (
            self._session.select(
                AuthPermission.code,
                AuthVerb.action,
                AuthResource.code.label("resource_code"),
            )
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .outerjoin(AuthVerb, AuthPermission.verb_id == AuthVerb.id)
            .where(AuthPermission.is_active == True)
            .fetch(as_model=PermissionRecord)
        )
        return permissions or []

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
