"""
System setting domain constants.
"""

from enum import Enum


class SettingNamespace(str, Enum):
    """Setting namespace for code-coupled readers."""

    FACILITY = "facility"


class FacilitySettingKey(str, Enum):
    """Facility settings read by application code."""

    TIMEZONE = "timezone"
    MAX_BOOKING_LINES = "max_booking_lines"
    RECURRING_BOOKING_AVAILABILITY_WINDOW = "recurring_booking_availability_window"
    MIN_RECURRING_BOOKING_WEEKS = "min_recurring_booking_weeks"
    PENDING_PAYMENT_HOLD_HOURS = "pending_payment_hold_hours"
    PENDING_PAYMENT_HOLD_DAYS = "pending_payment_hold_days"
    RECURRING_BOOKING_TEST_WINDOW_OVERRIDE = "recurring_booking_test_window_override"
    RECURRING_BOOKING_TEST_BOOKER_ALLOWLIST = "recurring_booking_test_booker_allowlist"


class RecurringAvailabilityUnit(str, Enum):
    """Duration unit for the Recurring Booking availability window."""

    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class SettingValueType(str, Enum):
    """Declared JSON shape for system_setting.value."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class SystemErrorCode(str, Enum):
    """Machine-readable system setting admin error codes for clients."""

    SETTING_NOT_FOUND = "SYSTEM_SETTING_NOT_FOUND"
    SETTING_KEY_EXISTS = "SYSTEM_SETTING_KEY_EXISTS"
    SETTING_IN_RECYCLE_BIN = "SYSTEM_SETTING_IN_RECYCLE_BIN"
    SETTING_BUILTIN_DELETE_FORBIDDEN = "SYSTEM_SETTING_BUILTIN_DELETE_FORBIDDEN"
