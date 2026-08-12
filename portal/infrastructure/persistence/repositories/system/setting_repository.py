"""
System setting repository.
"""
import json
from typing import Any, Optional
from uuid import UUID

from portal.domain.system.entities import Setting
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import SystemSetting


class SettingRepository:
    """SQLAlchemy-backed system setting repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _serialize_jsonb(value: Any) -> str:
        """asyncpg JSONB bind expects a JSON text string, not a raw Python value."""
        return json.dumps(value)

    def _base_select(self):
        return self._session.select(
            SystemSetting.id,
            SystemSetting.namespace,
            SystemSetting.setting_key,
            SystemSetting.value_type,
            SystemSetting.value,
            SystemSetting.is_built_in,
            SystemSetting.is_active,
            SystemSetting.remark,
            SystemSetting.created_at,
            SystemSetting.created_by,
            SystemSetting.updated_at,
            SystemSetting.updated_by,
            SystemSetting.is_deleted,
            SystemSetting.delete_reason,
        )

    async def get_by_id(
        self,
        setting_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> Optional[Setting]:
        query = self._base_select().where(SystemSetting.id == setting_id)
        if not include_deleted:
            query = query.where(SystemSetting.is_deleted == False)
        return await query.fetchrow(as_model=Setting)

    async def get_by_namespace_key(
        self,
        namespace: str,
        setting_key: str,
        *,
        include_deleted: bool = False,
    ) -> Optional[Setting]:
        query = (
            self._base_select()
            .where(SystemSetting.namespace == namespace)
            .where(SystemSetting.setting_key == setting_key)
        )
        if not include_deleted:
            query = query.where(SystemSetting.is_deleted == False)
        return await query.fetchrow(as_model=Setting)

    async def list_settings(
        self,
        namespace: Optional[str] = None,
        *,
        deleted: bool = False,
    ) -> list[Setting]:
        query = (
            self._base_select()
            .where(SystemSetting.is_deleted == deleted)
            .where(namespace is not None, lambda: SystemSetting.namespace == namespace)
            .order_by(SystemSetting.namespace, SystemSetting.setting_key)
        )
        items: list[Setting] = await query.fetch(as_model=Setting)
        return items or []

    async def update_value(
        self,
        setting_id: UUID,
        value: Any,
        remark: Optional[str] = None,
    ) -> int:
        values: dict[str, Any] = {"value": self._serialize_jsonb(value)}
        if remark is not None:
            values["remark"] = remark
        result = await (
            self._session.update(SystemSetting)
            .values(**values)
            .where(SystemSetting.id == setting_id)
            .where(SystemSetting.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def insert(self, payload: dict[str, Any]) -> None:
        insert_payload = {**payload, "value": self._serialize_jsonb(payload["value"])}
        await self._session.insert(SystemSetting).values(insert_payload).execute()

    async def insert_if_missing(self, payload: dict[str, Any]) -> bool:
        existing_id = await (
            self._session.select(SystemSetting.id)
            .where(SystemSetting.namespace == payload["namespace"])
            .where(SystemSetting.setting_key == payload["setting_key"])
            .where(SystemSetting.is_deleted == False)
            .fetchval()
        )
        if existing_id:
            return False
        await self.insert(payload)
        return True

    async def delete_soft(self, setting_id: UUID, reason: Optional[str]) -> int:
        result = await (
            self._session.update(SystemSetting)
            .values(is_deleted=True, delete_reason=reason)
            .where(SystemSetting.id == setting_id)
            .where(SystemSetting.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_hard(self, setting_id: UUID) -> int:
        result = await (
            self._session.delete(SystemSetting)
            .where(SystemSetting.id == setting_id)
            .execute()
        )
        return affected_rows(result)

    async def restore(self, setting_ids: list[UUID]) -> int:
        if not setting_ids:
            return 0
        result = await (
            self._session.update(SystemSetting)
            .values(is_deleted=False, delete_reason=None)
            .where(SystemSetting.id.in_(setting_ids))
            .where(SystemSetting.is_deleted == True)
            .execute()
        )
        return affected_rows(result)
