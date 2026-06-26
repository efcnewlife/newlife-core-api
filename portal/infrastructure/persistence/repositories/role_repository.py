"""
Role repository implementation.
"""
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa
from asyncpg import UniqueViolationError
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

from portal.libs.database import Session
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
from portal.application.rbac.commands import PagesQueryCommand
from portal.domain.rbac.entities import RoleDetail, RoleListItem


class RoleRepository:
    """SQLAlchemy-backed role repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _permissions_coalesced():
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
        return sa.func.coalesce(
            agg_permissions,
            sa.cast(sa.text("'{}'"), ARRAY(JSONB))
        ).label("permissions")

    def _detail_select(self):
        return self._session.select(
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
            self._permissions_coalesced(),
        ).select_from(AuthRole)

    def _detail_query(self, locale_id: Optional[UUID]):
        query = self._detail_select()
        if locale_id:
            return (
                query.outerjoin(
                    AuthRoleTranslation,
                    sa.and_(
                        AuthRoleTranslation.role_id == AuthRole.id,
                        AuthRoleTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
                .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
                .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
                .outerjoin(
                    AuthResourceTranslation,
                    sa.and_(
                        AuthResourceTranslation.resource_id == AuthResource.id,
                        AuthResourceTranslation.locale_id == locale_id,
                    ),
                )
                .outerjoin(
                    AuthPermissionTranslation,
                    sa.and_(
                        AuthPermissionTranslation.permission_id == AuthPermission.id,
                        AuthPermissionTranslation.locale_id == locale_id,
                    ),
                )
            )
        return (
            query.outerjoin(AuthRoleTranslation, sa.false())
            .outerjoin(AuthRolePermission, AuthRolePermission.role_id == AuthRole.id)
            .outerjoin(AuthPermission, AuthPermission.id == AuthRolePermission.permission_id)
            .outerjoin(AuthResource, AuthPermission.resource_id == AuthResource.id)
            .outerjoin(AuthResourceTranslation, sa.false())
            .outerjoin(AuthPermissionTranslation, sa.false())
        )

    def _active_roles_query(self, locale_id: Optional[UUID]):
        query = (
            self._session.select(
                AuthRole.id,
                AuthRole.code,
                sa.func.max(AuthRoleTranslation.name).label("name"),
            )
            .select_from(AuthRole)
        )
        if locale_id:
            return query.outerjoin(
                AuthRoleTranslation,
                sa.and_(
                    AuthRoleTranslation.role_id == AuthRole.id,
                    AuthRoleTranslation.locale_id == locale_id,
                ),
            )
        return query.outerjoin(AuthRoleTranslation, sa.false())

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[RoleDetail], int]:
        """
        Paginated role list.
        :param model:
        :param locale_id:
        :return:
        """
        items, count = await (
            self._detail_query(locale_id)
            .where(AuthRole.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    AuthRoleTranslation.name.ilike(f"%{model.keyword}%"),
                    AuthRole.code.ilike(f"%{model.keyword}%"),
                ),
            )
            .group_by(AuthRole.id)
            .order_by_with(
                tables=[AuthRole],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(
                no_order_by=False,
                as_model=RoleDetail,
            )
        )
        return items, count

    async def list_active_roles(self, locale_id: Optional[UUID]) -> list[RoleListItem]:
        """
        List active roles for admin dropdown.
        :param locale_id:
        :return:
        """
        roles: list[RoleListItem] = await (
            self._active_roles_query(locale_id)
            .where(AuthRole.is_active == True)
            .group_by(AuthRole.id)
            .fetch(as_model=RoleListItem)
        )
        return roles or []

    async def get_by_id(
        self,
        role_id: UUID,
        locale_id: Optional[UUID],
    ) -> Optional[RoleDetail]:
        """
        Fetch role detail by id.
        :param role_id:
        :param locale_id:
        :return:
        """
        role: Optional[RoleDetail] = await (
            self._detail_query(locale_id)
            .where(AuthRole.id == role_id)
            .group_by(AuthRole.id)
            .fetchrow(as_model=RoleDetail)
        )
        return role

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

    async def insert_role(self, payload: dict[str, Any]) -> None:
        """
        Insert auth_role row.
        :param payload:
        :return:
        """
        await (
            self._session.insert(AuthRole)
            .values(payload)
            .execute()
        )

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        """
        Upsert role translation rows.
        :param rows:
        :return:
        """
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

    async def insert_role_permissions(
        self,
        role_id: UUID,
        permission_ids: list[UUID],
    ) -> None:
        """
        Insert role-permission associations.
        :param role_id:
        :param permission_ids:
        :return:
        """
        if not permission_ids:
            return
        await (
            self._session.insert(AuthRolePermission)
            .values(
                [
                    {"role_id": role_id.hex, "permission_id": permission_id.hex}
                    for permission_id in permission_ids
                ]
            )
            .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
            .execute()
        )

    async def fetch_permission_ids_for_role(self, role_id: UUID) -> list[UUID]:
        """
        List permission ids assigned to a role.
        :param role_id:
        :return:
        """
        return await (
            self._session.select(AuthRolePermission.permission_id)
            .where(AuthRolePermission.role_id == role_id)
            .fetchvals()
        )

    async def upsert_role(self, role_id: UUID, values: dict[str, Any]) -> int:
        """
        Upsert role row; returns affected row count.
        :param role_id:
        :param values:
        :return:
        """
        result = await (
            self._session.insert(AuthRole)
            .values(id=role_id, **values)
            .on_conflict_do_update(
                index_elements=[AuthRole.id],
                set_=dict(
                    code=values["code"],
                    is_active=values["is_active"],
                ),
            )
            .execute()
        )
        return affected_rows(result)

    async def delete_role_permissions(
        self,
        role_id: UUID,
        permission_ids: list[UUID],
    ) -> None:
        """
        Remove role-permission associations.
        :param role_id:
        :param permission_ids:
        :return:
        """
        if not permission_ids:
            return
        await (
            self._session.delete(AuthRolePermission)
            .where(AuthRolePermission.role_id == role_id)
            .where(AuthRolePermission.permission_id.in_(permission_ids))
            .execute()
        )

    async def delete_all_role_permissions(self, role_id: UUID) -> None:
        """
        Remove all permissions from a role.
        :param role_id:
        :return:
        """
        await (
            self._session.delete(AuthRolePermission)
            .where(AuthRolePermission.role_id == role_id)
            .execute()
        )

    async def insert_role_permission_rows(self, rows: list[dict[str, Any]]) -> None:
        """
        Insert role-permission rows (UUID ids).
        :param rows:
        :return:
        """
        if not rows:
            return
        await (
            self._session.insert(AuthRolePermission)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["role_id", "permission_id"])
            .execute()
        )

    async def delete_soft(self, role_id: UUID, reason: Optional[str]) -> None:
        """
        Soft-delete role.
        :param role_id:
        :param reason:
        :return:
        """
        await (
            self._session.update(AuthRole)
            .values(is_deleted=True, delete_reason=reason)
            .where(AuthRole.id == role_id)
            .execute()
        )

    async def delete_hard(self, role_id: UUID) -> None:
        """
        Permanently delete role and its permissions.
        :param role_id:
        :return:
        """
        await self.delete_all_role_permissions(role_id)
        await (
            self._session.delete(AuthRole)
            .where(AuthRole.id == role_id)
            .execute()
        )

    async def restore_role(self, role_id: UUID) -> None:
        """
        Restore soft-deleted role.
        :param role_id:
        :return:
        """
        await (
            self._session.update(AuthRole)
            .values(is_deleted=False, delete_reason=None)
            .where(AuthRole.id == role_id)
            .execute()
        )

    async def list_user_role_codes(self, user_id: UUID) -> list[str]:
        """
        Role codes assigned to a user.
        :param user_id:
        :return:
        """
        role_codes = await (
            self._session.select(AuthRole.code)
            .join(AuthRole.users)
            .where(AuthUser.id == user_id)
            .where(AuthRole.is_deleted == False)
            .where(AuthUser.is_deleted == False)
            .order_by(AuthRole.code)
            .fetchvals()
        )
        return role_codes or []

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        return isinstance(exc, UniqueViolationError)
