"""
System setting application service.
"""

from typing import Any, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import ujson

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand
from portal.application.system.commands import CreateSettingCommand, UpdateSettingCommand
from portal.application.system.results import (
    CreateIdResult,
    RecurringBookingAvailabilityWindowResult,
    RecurringBookingTestBookerAllowlistResult,
    SettingListResult,
    SettingResult,
)
from portal.domain.system.constants import FacilitySettingKey, RecurringAvailabilityUnit, SettingNamespace, SettingValueType, SystemErrorCode
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
        if namespace == SettingNamespace.FACILITY.value:
            self._validate_facility_setting_value(setting_key, command.value)

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
        if row.namespace == SettingNamespace.FACILITY.value:
            self._validate_facility_setting_value(row.setting_key, command.value)
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

    @staticmethod
    def _parse_positive_int(value: Any, *, field_name: str) -> int:
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise BadRequestException(detail=f"{field_name} must be a positive integer")
        return value

    @classmethod
    def _parse_recurring_booking_availability_window(cls, value: Any) -> RecurringBookingAvailabilityWindowResult:
        if not isinstance(value, dict):
            raise BadRequestException(detail="facility.recurring_booking_availability_window must be an object")
        amount = cls._parse_positive_int(value.get("amount"), field_name="amount")
        unit = value.get("unit")
        allowed = {item.value for item in RecurringAvailabilityUnit}
        if unit not in allowed:
            raise BadRequestException(detail="unit must be days, weeks, or months")
        return RecurringBookingAvailabilityWindowResult(amount=amount, unit=unit)

    @staticmethod
    def _parse_test_booker_allowlist(value: Any) -> RecurringBookingTestBookerAllowlistResult:
        if not isinstance(value, dict):
            raise BadRequestException(detail="facility.recurring_booking_test_booker_allowlist must be an object")
        email_addresses = value.get("emailAddresses", [])
        email_suffixes = value.get("emailSuffixes", [])
        if not isinstance(email_addresses, list) or not all(isinstance(item, str) for item in email_addresses):
            raise BadRequestException(detail="emailAddresses must be an array of strings")
        if not isinstance(email_suffixes, list) or not all(isinstance(item, str) for item in email_suffixes):
            raise BadRequestException(detail="emailSuffixes must be an array of strings")
        normalized_addresses = [item.strip().lower() for item in email_addresses]
        normalized_suffixes = [item.strip().lower() for item in email_suffixes]
        if any(not suffix.startswith("@") or len(suffix) < 2 for suffix in normalized_suffixes):
            raise BadRequestException(detail="emailSuffixes entries must begin with '@' and name a complete domain")
        return RecurringBookingTestBookerAllowlistResult(email_addresses=normalized_addresses, email_suffixes=normalized_suffixes)

    @classmethod
    def _validate_facility_setting_value(cls, setting_key: str, value: Any) -> None:
        if setting_key == FacilitySettingKey.TIMEZONE.value:
            cls._validate_iana_timezone(value)
            return
        if setting_key == FacilitySettingKey.RECURRING_BOOKING_AVAILABILITY_WINDOW.value:
            cls._parse_recurring_booking_availability_window(value)
            return
        if setting_key in {FacilitySettingKey.MIN_RECURRING_BOOKING_WEEKS.value, FacilitySettingKey.PENDING_PAYMENT_HOLD_HOURS.value}:
            cls._parse_positive_int(value, field_name=setting_key)
            return
        if setting_key == FacilitySettingKey.RECURRING_BOOKING_TEST_WINDOW_OVERRIDE.value:
            if not isinstance(value, bool):
                raise BadRequestException(detail=f"{setting_key} must be a boolean")
            return
        if setting_key == FacilitySettingKey.RECURRING_BOOKING_TEST_BOOKER_ALLOWLIST.value:
            cls._parse_test_booker_allowlist(value)

    async def _read_facility_setting(self, setting_key: str, expected_type: str) -> Any:
        namespace = SettingNamespace.FACILITY.value
        cached = await self._cache.get_value(namespace, setting_key)
        if cached is not None:
            return self._coerce_jsonb_value(cached)

        row = await self._repository.get_by_namespace_key(namespace, setting_key)
        if not row or not row.is_active:
            raise NotFoundException(detail=f"facility.{setting_key} setting is not configured")
        if row.value_type != expected_type:
            raise BadRequestException(detail=f"facility.{setting_key} must have value_type {expected_type}")
        value = self._coerce_jsonb_value(row.value)
        await self._cache.set_value(namespace, setting_key, value)
        return value

    async def _read_facility_setting_lenient(self, setting_key: str, expected_type: str) -> Any:
        """Read a test-control facility setting; None when missing/inactive/wrong-typed (fail closed, never raises)."""
        namespace = SettingNamespace.FACILITY.value
        cached = await self._cache.get_value(namespace, setting_key)
        if cached is not None:
            return self._coerce_jsonb_value(cached)

        row = await self._repository.get_by_namespace_key(namespace, setting_key)
        if not row or not row.is_active or row.value_type != expected_type:
            return None
        value = self._coerce_jsonb_value(row.value)
        await self._cache.set_value(namespace, setting_key, value)
        return value

    @distributed_trace()
    async def get_recurring_booking_test_window_override(self) -> bool:
        value = await self._read_facility_setting_lenient(FacilitySettingKey.RECURRING_BOOKING_TEST_WINDOW_OVERRIDE.value, SettingValueType.BOOLEAN.value)
        return value is True

    @distributed_trace()
    async def get_recurring_booking_test_booker_allowlist(self) -> RecurringBookingTestBookerAllowlistResult:
        value = await self._read_facility_setting_lenient(FacilitySettingKey.RECURRING_BOOKING_TEST_BOOKER_ALLOWLIST.value, SettingValueType.OBJECT.value)
        if value is None:
            return RecurringBookingTestBookerAllowlistResult()
        try:
            return self._parse_test_booker_allowlist(value)
        except BadRequestException:
            return RecurringBookingTestBookerAllowlistResult()

    @distributed_trace()
    async def get_facility_timezone(self) -> ZoneInfo:
        timezone_name = await self._read_facility_setting(FacilitySettingKey.TIMEZONE.value, SettingValueType.STRING.value)
        self._validate_iana_timezone(timezone_name)
        return ZoneInfo(timezone_name)

    @distributed_trace()
    async def get_max_booking_lines(self) -> int:
        return int(await self._read_facility_setting(FacilitySettingKey.MAX_BOOKING_LINES.value, SettingValueType.NUMBER.value))

    @distributed_trace()
    async def get_recurring_booking_availability_window(self) -> RecurringBookingAvailabilityWindowResult:
        value = await self._read_facility_setting(FacilitySettingKey.RECURRING_BOOKING_AVAILABILITY_WINDOW.value, SettingValueType.OBJECT.value)
        return self._parse_recurring_booking_availability_window(value)

    @distributed_trace()
    async def get_min_recurring_booking_weeks(self) -> int:
        value = await self._read_facility_setting(FacilitySettingKey.MIN_RECURRING_BOOKING_WEEKS.value, SettingValueType.NUMBER.value)
        return self._parse_positive_int(value, field_name=FacilitySettingKey.MIN_RECURRING_BOOKING_WEEKS.value)

    @distributed_trace()
    async def get_pending_payment_hold_hours(self) -> int:
        value = await self._read_facility_setting(FacilitySettingKey.PENDING_PAYMENT_HOLD_HOURS.value, SettingValueType.NUMBER.value)
        return self._parse_positive_int(value, field_name=FacilitySettingKey.PENDING_PAYMENT_HOLD_HOURS.value)
