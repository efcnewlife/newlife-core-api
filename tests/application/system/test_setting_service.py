"""
Tests for SettingService.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.application.system.commands import CreateSettingCommand, UpdateSettingCommand
from portal.application.system.setting_service import SettingService
from portal.domain.system.constants import FacilitySettingKey, SettingNamespace, SettingValueType
from portal.domain.system.entities import Setting
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException


def _setting(
    *,
    namespace: str = SettingNamespace.FACILITY.value,
    setting_key: str = FacilitySettingKey.TIMEZONE.value,
    value_type: str = SettingValueType.STRING.value,
    value: Any = "America/Toronto",
    is_active: bool = True,
    is_built_in: bool = True,
    is_deleted: bool = False,
) -> Setting:
    now = datetime.now(timezone.utc)
    return Setting(
        id=uuid4(),
        namespace=namespace,
        setting_key=setting_key,
        value_type=value_type,
        value=value,
        is_built_in=is_built_in,
        is_active=is_active,
        remark=None,
        created_at=now,
        created_by=None,
        updated_at=now,
        updated_by=None,
        is_deleted=is_deleted,
        delete_reason=None,
    )


class StubSettingRepository:
    def __init__(self, rows: list[Setting] | None = None):
        self.rows = {row.id: row for row in (rows or [])}
        self.update_calls: list[dict] = []
        self.insert_calls: list[dict] = []
        self.delete_soft_calls: list[dict] = []
        self.delete_hard_calls: list[UUID] = []
        self.restore_calls: list[list[UUID]] = []

    async def get_by_id(self, setting_id, *, include_deleted: bool = False):
        row = self.rows.get(setting_id)
        if not row:
            return None
        if row.is_deleted and not include_deleted:
            return None
        return row

    async def get_by_namespace_key(self, namespace: str, setting_key: str, *, include_deleted: bool = False):
        for row in self.rows.values():
            if row.namespace == namespace and row.setting_key == setting_key:
                if row.is_deleted and not include_deleted:
                    continue
                return row
        return None

    async def list_settings(self, namespace: Optional[str] = None, *, deleted: bool = False):
        items = [row for row in self.rows.values() if row.is_deleted == deleted]
        if namespace is not None:
            items = [row for row in items if row.namespace == namespace]
        return items

    async def update_value(self, setting_id, value: Any, remark: Optional[str] = None) -> int:
        row = self.rows.get(setting_id)
        if not row or row.is_deleted:
            return 0
        self.update_calls.append({"setting_id": setting_id, "value": value, "remark": remark})
        row.value = value
        if remark is not None:
            row.remark = remark
        return 1

    async def insert(self, payload: dict[str, Any]) -> None:
        self.insert_calls.append(payload)
        row = _setting(
            namespace=payload["namespace"],
            setting_key=payload["setting_key"],
            value_type=payload["value_type"],
            value=payload["value"],
            is_active=payload.get("is_active", True),
            is_built_in=payload.get("is_built_in", False),
        )
        row.id = payload["id"]
        row.remark = payload.get("remark")
        self.rows[row.id] = row

    async def insert_if_missing(self, payload: dict[str, Any]) -> bool:
        return False

    async def delete_soft(self, setting_id, reason: Optional[str]) -> int:
        row = self.rows.get(setting_id)
        if not row or row.is_deleted:
            return 0
        self.delete_soft_calls.append({"setting_id": setting_id, "reason": reason})
        row.is_deleted = True
        row.delete_reason = reason
        return 1

    async def delete_hard(self, setting_id) -> int:
        if setting_id not in self.rows:
            return 0
        self.delete_hard_calls.append(setting_id)
        del self.rows[setting_id]
        return 1

    async def restore(self, setting_ids: list) -> int:
        self.restore_calls.append(list(setting_ids))
        count = 0
        for setting_id in setting_ids:
            row = self.rows.get(setting_id)
            if row and row.is_deleted:
                row.is_deleted = False
                row.delete_reason = None
                count += 1
        return count


class StubSettingCache:
    def __init__(self, cached: Any = None):
        self.cached = cached
        self.set_calls: list[tuple] = []
        self.invalidate_calls: list[tuple] = []

    async def get_value(self, namespace: str, setting_key: str):
        return self.cached

    async def set_value(self, namespace: str, setting_key: str, value: Any) -> None:
        self.set_calls.append((namespace, setting_key, value))
        self.cached = value

    async def invalidate(self, namespace: str, setting_key: str) -> None:
        self.invalidate_calls.append((namespace, setting_key))
        self.cached = None


@pytest.mark.asyncio
async def test_get_facility_timezone_happy_path():
    row = _setting(value="America/Toronto")
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    tz = await service.get_facility_timezone()
    assert isinstance(tz, ZoneInfo)
    assert str(tz) == "America/Toronto"


@pytest.mark.asyncio
async def test_get_facility_timezone_decodes_asyncpg_jsonb_string():
    # asyncpg returns JSONB strings as JSON text, e.g. '"America/Toronto"'.
    row = Setting.model_validate({**_setting().model_dump(), "value": '"America/Toronto"'})
    assert row.value == "America/Toronto"
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    tz = await service.get_facility_timezone()
    assert str(tz) == "America/Toronto"


@pytest.mark.asyncio
async def test_get_facility_timezone_decodes_cached_jsonb_string():
    cache = StubSettingCache(cached='"America/Toronto"')
    service = SettingService(StubSettingRepository([]), cache)
    tz = await service.get_facility_timezone()
    assert str(tz) == "America/Toronto"


@pytest.mark.asyncio
async def test_get_facility_timezone_uses_cache():
    cache = StubSettingCache(cached="America/Vancouver")
    service = SettingService(StubSettingRepository([]), cache)
    tz = await service.get_facility_timezone()
    assert str(tz) == "America/Vancouver"


@pytest.mark.asyncio
async def test_get_facility_timezone_missing():
    service = SettingService(StubSettingRepository([]), StubSettingCache())
    with pytest.raises(NotFoundException, match="facility.timezone"):
        await service.get_facility_timezone()


@pytest.mark.asyncio
async def test_get_facility_timezone_invalid_iana():
    row = _setting(value="Not/AZone")
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    with pytest.raises(BadRequestException, match="Invalid IANA timezone"):
        await service.get_facility_timezone()


@pytest.mark.asyncio
async def test_update_setting_rejects_wrong_value_type():
    row = _setting(value="America/Toronto")
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    with pytest.raises(BadRequestException, match="JSON string"):
        await service.update_setting(row.id, UpdateSettingCommand(value=123))


@pytest.mark.asyncio
async def test_update_setting_validates_timezone_and_invalidates_cache():
    row = _setting(value="America/Toronto")
    repo = StubSettingRepository([row])
    cache = StubSettingCache(cached="America/Toronto")
    service = SettingService(repo, cache)
    result = await service.update_setting(row.id, UpdateSettingCommand(value="America/Vancouver", remark="west"))
    assert result.value == "America/Vancouver"
    assert result.remark == "west"
    assert cache.invalidate_calls == [(row.namespace, row.setting_key)]


@pytest.mark.asyncio
async def test_create_setting_happy_path():
    repo = StubSettingRepository([])
    service = SettingService(repo, StubSettingCache())
    result = await service.create_setting(CreateSettingCommand(namespace="ops", setting_key="feature_flag", value_type="boolean", value=True))
    assert result.id in repo.rows
    assert repo.rows[result.id].is_built_in is False
    assert len(repo.insert_calls) == 1


@pytest.mark.asyncio
async def test_create_setting_duplicate_active():
    row = _setting(namespace="ops", setting_key="flag", is_built_in=False)
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    with pytest.raises(ConflictErrorException, match="already exist"):
        await service.create_setting(CreateSettingCommand(namespace="ops", setting_key="flag", value_type="string", value="x"))


@pytest.mark.asyncio
async def test_create_setting_duplicate_in_recycle():
    row = _setting(namespace="ops", setting_key="flag", is_built_in=False, is_deleted=True)
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    with pytest.raises(ConflictErrorException, match="recycle"):
        await service.create_setting(CreateSettingCommand(namespace="ops", setting_key="flag", value_type="string", value="x"))


@pytest.mark.asyncio
async def test_delete_built_in_blocked():
    row = _setting(is_built_in=True)
    service = SettingService(StubSettingRepository([row]), StubSettingCache())
    with pytest.raises(BadRequestException, match="Built-in"):
        await service.delete_setting(row.id, DeleteCommand(reason="nope"))


@pytest.mark.asyncio
async def test_delete_soft_and_restore():
    row = _setting(namespace="ops", setting_key="flag", is_built_in=False)
    repo = StubSettingRepository([row])
    cache = StubSettingCache()
    service = SettingService(repo, cache)
    await service.delete_setting(row.id, DeleteCommand(reason="cleanup"))
    assert row.is_deleted is True
    assert cache.invalidate_calls == [("ops", "flag")]
    await service.restore_settings(BulkIdsCommand(ids=[row.id]))
    assert row.is_deleted is False
