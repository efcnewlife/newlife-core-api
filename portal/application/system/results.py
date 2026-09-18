"""
System setting application results.
"""

from typing import Any

from pydantic import BaseModel, Field

from portal.domain.common.mixins import AuditModel, RemarkModel, UUIDModel


class CreateIdResult(UUIDModel):
    """Created setting id."""


class SettingResult(UUIDModel, AuditModel, RemarkModel):
    """Setting detail/list item for application layer."""

    namespace: str = Field(...)
    setting_key: str = Field(...)
    value_type: str = Field(...)
    value: Any = Field(...)
    is_built_in: bool = Field(default=False)
    is_active: bool = Field(default=True)


class SettingListResult(BaseModel):
    """List of settings."""

    items: list[SettingResult] = Field(default_factory=list)


class RecurringBookingAvailabilityWindowResult(BaseModel):
    """Parsed facility.recurring_booking_availability_window value."""

    amount: int = Field(...)
    unit: str = Field(...)


class RecurringBookingTestBookerAllowlistResult(BaseModel):
    """Parsed, normalized facility.recurring_booking_test_booker_allowlist value."""

    email_addresses: list[str] = Field(default_factory=list)
    email_suffixes: list[str] = Field(default_factory=list)
