"""
Resource repository implementation.
"""
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from sqlalchemy.orm import aliased

from portal.libs.database import Session
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
from portal.domain.rbac.entities import ResourceDetail, ResourceItem


class ResourceRepository:
    """SQLAlchemy-backed resource repository."""

    def __init__(self, session: Session):
        self._session = session

    def _detail_query(self, locale_id: Optional[UUID]):
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
                ).label("parent"),
            )
            .select_from(AuthResource)
        )
        if locale_id:
            return (
                query.outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(pr_parent, AuthResource.pid == pr_parent.id)
                .outerjoin(
                    parent_res_tr,
                    sa.and_(
                        parent_res_tr.resource_id == pr_parent.id,
                        parent_res_tr.locale_id == locale_id,
                    ),
                )
            )
        return (
            query.outerjoin(AuthResourceTranslation, sa.false())
            .outerjoin(pr_parent, AuthResource.pid == pr_parent.id)
            .outerjoin(parent_res_tr, sa.false())
        )

    def _menu_query(self, locale_id: Optional[UUID]):
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
                AuthResource.is_deleted,
            )
            .select_from(AuthResource)
        )
        if locale_id:
            return query.outerjoin(
                AuthResourceTranslation,
                sa.and_(
                    AuthResourceTranslation.resource_id == AuthResource.id,
                    AuthResourceTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(AuthResourceTranslation, sa.false())

    async def get_by_id(
        self,
        resource_id: UUID,
        locale_id: Optional[UUID],
    ) -> Optional[ResourceDetail]:
        """
        Fetch resource detail by id.
        :param resource_id:
        :param locale_id:
        :return:
        """
        return await (
            self._detail_query(locale_id)
            .where(AuthResource.id == resource_id)
            .fetchrow(as_model=ResourceDetail)
        )

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

    async def insert_resource(self, payload: dict[str, Any]) -> None:
        """
        Insert auth_resource row.
        :param payload:
        :return:
        """
        await (
            self._session.insert(AuthResource)
            .values(payload)
            .execute()
        )

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        """
        Upsert resource translation rows.
        :param rows:
        :return:
        """
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

    async def update_resource(
        self,
        resource_id: UUID,
        values: dict[str, Any],
    ) -> int:
        """
        Update resource row; returns affected row count.
        :param resource_id:
        :param values:
        :return:
        """
        result = await (
            self._session.update(AuthResource)
            .values(**values)
            .where(AuthResource.id == resource_id)
            .execute()
        )
        return affected_rows(result)

    async def change_parent(self, resource_id: UUID, pid: UUID) -> None:
        """
        Update resource parent id.
        :param resource_id:
        :param pid:
        :return:
        """
        await (
            self._session.update(AuthResource)
            .values(pid=pid)
            .where(AuthResource.id == resource_id)
            .execute()
        )

    async def update_sequence(self, resource_id: UUID, sequence: float) -> None:
        """
        Update resource sequence.
        :param resource_id:
        :param sequence:
        :return:
        """
        await (
            self._session.update(AuthResource)
            .values(sequence=sequence)
            .where(AuthResource.id == resource_id)
            .execute()
        )

    async def delete_soft(self, resource_id: UUID, reason: Optional[str]) -> None:
        """
        Soft-delete resource and its direct children.
        :param resource_id:
        :param reason:
        :return:
        """
        await (
            self._session.update(AuthResource)
            .values(is_deleted=True, delete_reason=reason)
            .where(sa.or_(AuthResource.id == resource_id, AuthResource.pid == resource_id))
            .execute()
        )

    async def delete_hard(self, resource_id: UUID) -> None:
        """
        Permanently delete resource row.
        :param resource_id:
        :return:
        """
        await (
            self._session.delete(AuthResource)
            .where(AuthResource.id == resource_id)
            .execute()
        )

    async def restore_resource_tree(self, resource_id: UUID) -> None:
        """
        Restore resource and its direct children.
        :param resource_id:
        :return:
        """
        await (
            self._session.update(AuthResource)
            .values(is_deleted=False, delete_reason=None)
            .where(sa.or_(AuthResource.id == resource_id, AuthResource.pid == resource_id))
            .execute()
        )

    async def list_menus(
        self,
        is_deleted: bool,
        locale_id: Optional[UUID],
    ) -> list[ResourceItem]:
        """
        List resources for admin menus.
        :param is_deleted:
        :param locale_id:
        :return:
        """
        resources: list[ResourceItem] = await (
            self._menu_query(locale_id)
            .where(
                is_deleted == True,
                lambda: sa.or_(
                    AuthResource.is_deleted == is_deleted,
                    sa.and_(AuthResource.pid.is_(None), AuthResource.is_deleted == False),
                ),
            )
            .where(is_deleted == False, lambda: AuthResource.is_deleted == is_deleted)
            .order_by(AuthResource.sequence)
            .fetch(as_model=ResourceItem)
        )
        return resources or []

    async def list_by_user_id(
        self,
        user_id: UUID,
        locale_id: Optional[UUID],
    ) -> list[ResourceItem]:
        """
        List visible resources granted to a user via roles.
        :param user_id:
        :param locale_id:
        :return:
        """
        user_resources_subquery = (
            self._session.select(
                AuthResource.id.label("resource_id"),
                AuthResource.pid.label("parent_id"),
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
            .where(
                sa.or_(
                    AuthRolePermission.expire_date.is_(None),
                    AuthRolePermission.expire_date > sa.func.now(),
                )
            )
            .subquery()
        )
        resources: list[ResourceItem] = await (
            self._menu_query(locale_id)
            .where(
                sa.or_(
                    AuthResource.id.in_(
                        sa.select(user_resources_subquery.c.resource_id)
                    ),
                    AuthResource.id.in_(
                        sa.select(user_resources_subquery.c.parent_id)
                        .where(user_resources_subquery.c.parent_id.isnot(None))
                    ),
                )
            )
            .where(AuthResource.is_deleted == False)
            .distinct()
            .order_by(AuthResource.sequence)
            .fetch(as_model=ResourceItem)
        )
        return resources or []

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
