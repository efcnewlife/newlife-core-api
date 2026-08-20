"""
System setting application service.
"""

from typing import Any, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import ujson

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.application.system.commands import CreateSettingCommand, UpdateSettingCommand
from portal.application.system.results import CreateIdResult, SettingListResult, SettingResult
from portal.domain.system.constants import FacilitySettingKey, SettingNamespace, SettingValueType, SystemErrorCode
from portal.domain.system.entities import Setting
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.cache.setting_cache import SettingCache
from portal.infrastructure.persistence.repositories.system.setting_repository import SettingRepository
from portal.libs.tracing.distributed_trace import distributed_trace


class SettingService:
    """Read/create/update/delete system settings; resolve facility timezone."""

    def __init__(self, setting_repository: SettingRepository, setting_cache: SettingCache):
        self._repository = setting_repository
        self._cache = setting_cache

    @staticmethod
    def _to_result(row: Setting) -> SettingResult:
        return SettingResult.model_validate(row.model_dump())

    @staticmethod
    def _coerce_jsonb_value(value: Any) -> Any:
        """Decode cached/asyncpg JSONB text into a Python value when needed."""
        if isinstance(value, str):
            try:
                return ujson.loads(value)
            except ujson.JSONDecodeError:
                return value
        return value

    @staticmethod
    def _validate_value_type(value_type: str, value: Any) -> None:
        if value_type == SettingValueType.STRING.value:
            if not isinstance(value, str):
                raise BadRequestException(detail="value must be a JSON string")
            return
        if value_type == SettingValueType.NUMBER.value:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise BadRequestException(detail="value must be a JSON number")
            return
        if value_type == SettingValueType.BOOLEAN.value:
            if not isinstance(value, bool):
                raise BadRequestException(detail="value must be a JSON boolean")
            return
        if value_type == SettingValueType.OBJECT.value:
            if not isinstance(value, dict):
                raise BadRequestException(detail="value must be a JSON object")
            return
        if value_type == SettingValueType.ARRAY.value:
            if not isinstance(value, list):
                raise BadRequestException(detail="value must be a JSON array")
            return
        raise BadRequestException(detail=f"Unsupported value_type: {value_type}")

    @staticmethod
    def _assert_value_type_enum(value_type: str) -> None:
        allowed = {item.value for item in SettingValueType}
        if value_type not in allowed:
            raise BadRequestException(detail=f"Unsupported value_type: {value_type}")

    @distributed_trace()
    async def list_settings(self, namespace: Optional[str] = None, *, deleted: bool = False) -> SettingListResult:
        rows = await self._repository.list_settings(namespace=namespace, deleted=deleted)
        return SettingListResult(items=[self._to_result(row) for row in rows])

    @distributed_trace()
    async def get_setting_by_id(self, setting_id: UUID) -> SettingResult:
        row = await self._repository.get_by_id(setting_id)
        if not row:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        return self._to_result(row)

    @distributed_trace()
    async def get_setting_by_key(self, namespace: str, setting_key: str) -> SettingResult:
        row = await self._repository.get_by_namespace_key(namespace, setting_key)
        if not row or not row.is_active:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        return self._to_result(row)

    @distributed_trace()
    async def create_setting(self, command: CreateSettingCommand) -> CreateIdResult:
        namespace = command.namespace.strip()
        setting_key = command.setting_key.strip()
        if not namespace or not setting_key:
            raise BadRequestException(detail="namespace and setting_key are required")
        self._assert_value_type_enum(command.value_type)
        self._validate_value_type(command.value_type, command.value)
        if namespace == SettingNamespace.FACILITY.value and setting_key == FacilitySettingKey.TIMEZONE.value:
            self._validate_iana_timezone(command.value)

        existing = await self._repository.get_by_namespace_key(namespace, setting_key, include_deleted=True)
        if existing:
            if existing.is_deleted:
                raise ConflictErrorException(
                    detail="Setting key exists in recycle bin; restore it instead", error_code=SystemErrorCode.SETTING_IN_RECYCLE_BIN.value
                )
            raise ConflictErrorException(detail="Setting namespace and key already exist", error_code=SystemErrorCode.SETTING_KEY_EXISTS.value)

        setting_id = uuid4()
        await self._repository.insert(
            dict(
                id=setting_id,
                namespace=namespace,
                setting_key=setting_key,
                value_type=command.value_type,
                value=command.value,
                is_built_in=False,
                is_active=command.is_active,
                remark=command.remark,
            )
        )
        return CreateIdResult(id=setting_id)

    @distributed_trace()
    async def update_setting(self, setting_id: UUID, command: UpdateSettingCommand) -> SettingResult:
        row = await self._repository.get_by_id(setting_id)
        if not row:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        self._validate_value_type(row.value_type, command.value)
        if row.namespace == SettingNamespace.FACILITY.value and row.setting_key == FacilitySettingKey.TIMEZONE.value:
            self._validate_iana_timezone(command.value)
        updated = await self._repository.update_value(setting_id=setting_id, value=command.value, remark=command.remark)
        if updated < 1:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        await self._cache.invalidate(row.namespace, row.setting_key)
        refreshed = await self._repository.get_by_id(setting_id)
        if not refreshed:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        return self._to_result(refreshed)

    @distributed_trace()
    async def delete_setting(self, setting_id: UUID, command: DeleteCommand) -> None:
        row = await self._repository.get_by_id(setting_id, include_deleted=command.permanent)
        if not row:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        if row.is_built_in:
            raise BadRequestException(detail="Built-in settings cannot be deleted", error_code=SystemErrorCode.SETTING_BUILTIN_DELETE_FORBIDDEN.value)
        if command.permanent:
            affected = await self._repository.delete_hard(setting_id)
        else:
            if row.is_deleted:
                raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
            affected = await self._repository.delete_soft(setting_id, command.reason)
        if affected < 1:
            raise NotFoundException(detail="Setting not found", error_code=SystemErrorCode.SETTING_NOT_FOUND.value)
        await self._cache.invalidate(row.namespace, row.setting_key)

    @distributed_trace()
    async def restore_settings(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            return
        rows = []
        for setting_id in command.ids:
            row = await self._repository.get_by_id(setting_id, include_deleted=True)
            if row and row.is_deleted:
                rows.append(row)
        affected = await self._repository.restore(command.ids)
        if affected < 1:
            raise NotFoundException(detail="No deleted settings found to restore")
        for row in rows:
            await self._cache.invalidate(row.namespace, row.setting_key)

    @staticmethod
    def _validate_iana_timezone(value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            raise BadRequestException(detail="timezone value must be a non-empty IANA string")
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise BadRequestException(detail=f"Invalid IANA timezone: {value}") from error

    @distributed_trace()
    async def get_facility_timezone(self) -> ZoneInfo:
        namespace = SettingNamespace.FACILITY.value
        setting_key = FacilitySettingKey.TIMEZONE.value
        cached = await self._cache.get_value(namespace, setting_key)
        if cached is not None:
            timezone_name = self._coerce_jsonb_value(cached)
            self._validate_iana_timezone(timezone_name)
            return ZoneInfo(timezone_name)

        row = await self._repository.get_by_namespace_key(namespace, setting_key)
        if not row or not row.is_active:
            raise NotFoundException(detail="facility.timezone setting is not configured")
        if row.value_type != SettingValueType.STRING.value:
            raise BadRequestException(detail="facility.timezone must have value_type string")
        timezone_name = self._coerce_jsonb_value(row.value)
        self._validate_iana_timezone(timezone_name)
        await self._cache.set_value(namespace, setting_key, timezone_name)
        return ZoneInfo(timezone_name)
