"""
RBAC domain ports.
"""
from typing import Any, Optional, Protocol
from uuid import UUID

from portal.application.rbac.commands import (
    AssignRolePermissionsCommand,
    PagesQueryCommand,
    PermissionPagesQueryCommand,
)
from portal.application.rbac.results import (
    PermissionDetailResult,
    PermissionListResult,
    PermissionPageResult,
    RoleDetailResult,
    RoleListResult,
    RolePageResult,
    VerbListResult,
)
from portal.application.auth.results import UserSensitive
from portal.domain.rbac.entities import PermissionListItem, PermissionRecord, VerbListItem


class VerbRepositoryPort(Protocol):
    """Load verbs for a locale."""

    async def list_active_by_locale(self, locale_id: UUID) -> list[VerbListItem]:
        ...


class VerbListCachePort(Protocol):
    """Redis cache for verb list by locale."""

    async def get(self, locale_id: UUID) -> Optional[list[VerbListItem]]:
        ...

    async def set(self, locale_id: UUID, items: list[VerbListItem]) -> None:
        ...


class PermissionRepositoryPort(Protocol):
    """Load and mutate permissions."""

    async def get_by_id(
        self,
        permission_id: UUID,
        locale_id: Optional[UUID],
    ) -> Optional[Any]:
        ...

    async def fetch_pages(
        self,
        command: PermissionPagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[Any], int]:
        ...

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        ...

    async def insert_permission(self, payload: dict[str, Any]) -> None:
        ...

    async def upsert_translations(self, rows: list[dict[str, Any]]) -> None:
        ...

    async def update_permission(
        self,
        permission_id: UUID,
        values: dict[str, Any],
    ) -> int:
        ...

    async def delete_hard(self, permission_id: UUID) -> int:
        ...

    async def delete_soft(self, permission_id: UUID, reason: Optional[str]) -> int:
        ...

    async def restore_permissions(self, permission_ids: list[UUID]) -> None:
        ...

    async def list_for_locale(self, locale_id: UUID) -> list[PermissionListItem]:
        ...

    async def list_user_role_permissions(self, user_id: UUID) -> list[PermissionRecord]:
        ...

    async def list_all_permissions(self) -> list[PermissionRecord]:
        ...

    @staticmethod
    def is_unique_violation(exc: Exception) -> bool:
        ...


class PermissionCachePort(Protocol):
    """Redis cache for user permissions and admin permission list."""

    async def get_permission_list_json(self, locale_id: UUID) -> str | None:
        ...

    async def set_permission_list_json(self, locale_id: UUID, payload_json: str) -> None:
        ...

    async def clear_user_permissions_cache(self, user_id: UUID) -> None:
        ...

    async def init_user_permissions_cache(
        self,
        user_id: UUID,
        permissions: list[PermissionRecord],
        expire: int,
    ) -> list[str]:
        ...


class RoleRepositoryPort(Protocol):
    """Load and mutate roles."""

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        ...

    async def get_role_pages(
        self,
        command: PagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[Any], int]:
        ...

    async def get_role_list(self, locale_id: Optional[UUID]) -> list[Any]:
        ...

    async def get_by_id(self, role_id: UUID, locale_id: Optional[UUID]) -> Optional[Any]:
        ...


class ResourceRepositoryPort(Protocol):
    """Load and mutate resources."""

    async def fetch_active_locale_ids(self, locale_ids: list[UUID]) -> set[UUID]:
        ...


class RoleCachePort(Protocol):
    """Redis cache for user roles."""

    async def init_user_roles_cache(
        self,
        user_id: UUID,
        role_codes: list[str],
        expire: int,
    ) -> list[str]:
        ...

    async def clear_user_roles_cache(self, user_id: UUID) -> None:
        ...


class RbacAuditPort(Protocol):
    """RBAC audit log writer."""

    def create_log(self, *args, **kwargs) -> None:
        ...
