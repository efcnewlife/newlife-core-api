"""
Seed rows for public.system_setting (insert-if-missing only).
"""

from portal.domain.system.constants import FacilitySettingKey, SettingNamespace, SettingValueType

seed_system_settings: list[dict] = [
    {
        "namespace": SettingNamespace.FACILITY.value,
        "setting_key": FacilitySettingKey.TIMEZONE.value,
        "value_type": SettingValueType.STRING.value,
        "value": "America/Toronto",
        "is_built_in": True,
        "is_active": True,
        "remark": "Org-level IANA timezone for facility wall-clock rules",
    },
    {
        "namespace": SettingNamespace.FACILITY.value,
        "setting_key": FacilitySettingKey.MAX_BOOKING_LINES.value,
        "value_type": SettingValueType.NUMBER.value,
        "value": 10,
        "is_built_in": True,
        "is_active": True,
        "remark": "Max Booking lines (rooms) allowed on one booking",
    },
]
