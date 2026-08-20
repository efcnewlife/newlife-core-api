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
