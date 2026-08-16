"""
System setting domain ports.
"""

from typing import Any, Optional, Protocol
from uuid import UUID

from portal.domain.system.entities import Setting


class SettingRepositoryPort(Protocol):
    """Load and update system settings."""

    async def get_by_id(self, setting_id: UUID, *, include_deleted: bool = False) -> Optional[Setting]: ...

    async def get_by_namespace_key(self, namespace: str, setting_key: str, *, include_deleted: bool = False) -> Optional[Setting]: ...

    async def list_settings(self, namespace: Optional[str] = None, *, deleted: bool = False) -> list[Setting]: ...

    async def update_value(self, setting_id: UUID, value: Any, remark: Optional[str] = None) -> int: ...

    async def insert(self, payload: dict[str, Any]) -> None: ...

    async def insert_if_missing(self, payload: dict[str, Any]) -> bool:
        """Insert row when namespace+key is absent. Return True if inserted."""
        ...

    async def delete_soft(self, setting_id: UUID, reason: Optional[str]) -> int: ...

    async def delete_hard(self, setting_id: UUID) -> int: ...

    async def restore(self, setting_ids: list[UUID]) -> int: ...
