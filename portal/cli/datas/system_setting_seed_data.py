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
    {
        "namespace": SettingNamespace.FACILITY.value,
        "setting_key": FacilitySettingKey.RECURRING_BOOKING_AVAILABILITY_WINDOW.value,
        "value_type": SettingValueType.OBJECT.value,
        "value": {"amount": 4, "unit": "weeks"},
        "is_built_in": True,
        "is_active": True,
        "remark": "Duration after Dec 1 / Jun 1 during which a Recurring Booking period accepts new Series",
    },
    {
        "namespace": SettingNamespace.FACILITY.value,
        "setting_key": FacilitySettingKey.MIN_RECURRING_BOOKING_WEEKS.value,
        "value_type": SettingValueType.NUMBER.value,
        "value": 4,
        "is_built_in": True,
        "is_active": True,
        "remark": "Minimum unexcluded weekly Recurring Booking occurrences",
    },
    {
        "namespace": SettingNamespace.FACILITY.value,
        "setting_key": FacilitySettingKey.PENDING_PAYMENT_HOLD_HOURS.value,
        "value_type": SettingValueType.NUMBER.value,
        "value": 72,
        "is_built_in": True,
        "is_active": True,
        "remark": "Hours a Pending-payment Series reserves occupancy before expiry",
    },
]
