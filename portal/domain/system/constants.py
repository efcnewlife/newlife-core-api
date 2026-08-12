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
