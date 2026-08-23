"""
Facility booking application results.
"""

from datetime import date as DateType
from datetime import datetime, time
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.application.content.results import FileGridItemResult
from portal.application.org.results import (
    CreateIdResult,
    MinistryDetailResult,
    MinistryListItemResult,
    MinistryListResult,
    MinistryPageResult,
    TranslationItemResult,
)
from portal.domain.common.mixins import JsonStringParseModel, UUIDBaseModel
from portal.domain.facility.constants import RentalRateBillingUnit
from portal.domain.facility.rate_applicability import coerce_applicability_from_db


class RoomListItemResult(UUIDBaseModel):
    """Room list row."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None)
    is_active: bool = Field(default=True)


class RoomDetailResult(UUIDBaseModel):
    """Room detail."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    description: Optional[str] = Field(default=None)
    translations: list[TranslationItemResult] = Field(default_factory=list)
    files: list[FileGridItemResult] = Field(default_factory=list)


class RoomPageResult(BaseModel):
    """Paginated rooms."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RoomDetailResult] = Field(default_factory=list)


class RoomListResult(BaseModel):
    """Active rooms dropdown."""

    items: list[RoomListItemResult] = Field(default_factory=list)


class RoomSlotTemplateResult(UUIDBaseModel):
    """Room slot template row."""

    facility_id: UUID = Field(...)
    name: str = Field(...)
    days_of_week_mask: int = Field(...)
    start_time: time = Field(...)
    end_time: time = Field(...)
    slot_duration_minutes: int = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[DateType] = Field(default=None)
    effective_to: Optional[DateType] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)


class RoomSlotTemplatePageResult(BaseModel):
    """Paginated slot templates."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RoomSlotTemplateResult] = Field(default_factory=list)


class RoomSlotTemplateListResult(BaseModel):
    """Slot template list."""

    items: list[RoomSlotTemplateResult] = Field(default_factory=list)


class RoomBlackoutResult(UUIDBaseModel):
    """Room blackout row."""

    facility_id: Optional[UUID] = Field(default=None)
    name: str = Field(...)
    reason: str = Field(...)
    kind: str = Field(...)
    blackout_date: Optional[DateType] = Field(default=None)
    days_of_week_mask: Optional[int] = Field(default=None)
    start_time: time = Field(...)
    end_time: time = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[DateType] = Field(default=None)
    effective_to: Optional[DateType] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)


class RoomBlackoutPageResult(BaseModel):
    """Paginated room blackouts."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RoomBlackoutResult] = Field(default_factory=list)


class RoomBlackoutListResult(BaseModel):
    """Room blackout list."""

    items: list[RoomBlackoutResult] = Field(default_factory=list)


class RentalRateTemplateResult(UUIDBaseModel):
    """Rental rate template row."""

    name: str = Field(...)
    billing_unit: str = Field(...)
    applicability: Optional[dict] = Field(default=None)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)

    @field_validator("applicability", mode="before")
    @classmethod
    def parse_applicability_from_db(cls, value: Any) -> Optional[dict]:
        return coerce_applicability_from_db(value)


class RentalRateTemplatePageResult(BaseModel):
    """Paginated rental rate templates."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RentalRateTemplateResult] = Field(default_factory=list)


class RentalRateTemplateListResult(BaseModel):
    """Rental rate template list."""

    items: list[RentalRateTemplateResult] = Field(default_factory=list)


class RentalRateResult(UUIDBaseModel):
    """Rental rate binding with joined template fields for pricing/admin."""

    facility_id: Optional[UUID] = Field(default=None)
    template_id: UUID = Field(...)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    # Joined from template (pricing / embed)
    unit_amount: Decimal = Field(...)
    currency: str = Field(...)
    template_name: Optional[str] = Field(default=None)
    billing_unit: Optional[str] = Field(default=None)
    applicability: Optional[dict] = Field(default=None)
    is_default: bool = Field(default=False)
    template_is_active: bool = Field(default=True)

    @field_validator("applicability", mode="before")
    @classmethod
    def parse_applicability_from_db(cls, value: Any) -> Optional[dict]:
        return coerce_applicability_from_db(value)


class RentalRatePageResult(BaseModel):
    """Paginated rental rates."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[RentalRateResult] = Field(default_factory=list)


class RentalRateListResult(BaseModel):
    """Rental rate list."""

    items: list[RentalRateResult] = Field(default_factory=list)


class DiscountRuleResult(UUIDBaseModel):
    """Discount rule row."""

    code: str = Field(...)
    percent_off: Decimal = Field(...)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class DiscountRuleListResult(BaseModel):
    """Discount rules list."""

    items: list[DiscountRuleResult] = Field(default_factory=list)


class SurchargeResult(UUIDBaseModel):
    """Surcharge row."""

    code: str = Field(...)
    charge_type: str = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(...)
    is_active: bool = Field(default=True)
    applies_to_booking_type: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class SurchargeListResult(BaseModel):
    """Surcharge list."""

    items: list[SurchargeResult] = Field(default_factory=list)


class PolicySettingResult(UUIDBaseModel):
    """Policy setting row."""

    setting_key: str = Field(...)
    facility_id: Optional[UUID] = Field(default=None)
    amount: Decimal = Field(...)
    currency: str = Field(...)
    is_active: bool = Field(default=True)
    created_at: Optional[datetime] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)


class PolicySettingListResult(BaseModel):
    """Policy settings list."""

    items: list[PolicySettingResult] = Field(default_factory=list)


class PreviewQuoteRoomLineResult(BaseModel):
    """Quoted room line with rule snapshot fields."""

    facility_id: UUID = Field(...)
    billed_hours: Decimal = Field(...)
    rental_rate_name: str = Field(default="")
    billing_unit: str = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    applicability: Optional[dict] = Field(default=None)
    is_default: bool = Field(default=False)
    line_subtotal: Decimal = Field(...)


class PreviewQuoteResult(BaseModel):
    """Preview quote totals."""

    subtotal_amount: Decimal = Field(...)
    discount_percent: Decimal = Field(...)
    discount_amount: Decimal = Field(...)
    surcharge_amount: Decimal = Field(...)
    quoted_amount: Decimal = Field(...)
    currency: str = Field(...)
    room_lines: list[PreviewQuoteRoomLineResult] = Field(default_factory=list)


class BookingRoomLineResult(UUIDBaseModel):
    """Booking room line detail with rule snapshot."""

    facility_id: UUID = Field(...)
    facility_name: Optional[str] = Field(default=None)
    facility_code: Optional[str] = Field(default=None)
    sequence: int = Field(default=0)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    billed_hours: Optional[Decimal] = Field(default=None)
    rental_rate_name: Optional[str] = Field(default=None)
    billing_unit: Optional[str] = Field(default=None)
    unit_amount: Optional[Decimal] = Field(default=None)
    currency: Optional[str] = Field(default=None)
    applicability: Optional[dict] = Field(default=None)
    is_default: Optional[bool] = Field(default=None)
    line_subtotal: Optional[Decimal] = Field(default=None)

    @field_validator("applicability", mode="before")
    @classmethod
    def parse_applicability_from_db(cls, value: Any) -> Optional[dict]:
        return coerce_applicability_from_db(value)


class BookingSlotResult(UUIDBaseModel):
    """Booking slot row."""

    facility_id: UUID = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    status: str = Field(...)


class BookingListItemResult(UUIDBaseModel):
    """Booking list row."""

    user_id: UUID = Field(...)
    user_email: Optional[str] = Field(default=None)
    user_display_name: Optional[str] = Field(default=None)
    facility_id: Optional[UUID] = Field(default=None)
    facility_name: Optional[str] = Field(default=None)
    facility_ids: list[UUID] = Field(default_factory=list)
    facility_names: list[str] = Field(default_factory=list)
    booking_type: str = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    status: str = Field(...)
    quoted_amount: Optional[Decimal] = Field(default=None)
    currency: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)


class BookingDetailResult(UUIDBaseModel):
    """Booking detail with rooms and slots."""

    user_id: UUID = Field(...)
    user_email: Optional[str] = Field(default=None)
    user_display_name: Optional[str] = Field(default=None)
    facility_id: Optional[UUID] = Field(default=None)
    ministry_id: Optional[UUID] = Field(default=None)
    booking_type: str = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    recurrence_rule: Optional[str] = Field(default=None, description="iCal RRULE string (RFC 5545); series anchor is start_at")
    recurrence_end_at: Optional[datetime] = Field(default=None, description="Recurrence series end")
    status: str = Field(...)
    is_mission_aligned: bool = Field(default=False)
    subtotal_amount: Optional[Decimal] = Field(default=None)
    discount_percent: Optional[Decimal] = Field(default=None)
    discount_amount: Optional[Decimal] = Field(default=None)
    surcharge_amount: Optional[Decimal] = Field(default=None)
    quoted_amount: Optional[Decimal] = Field(default=None)
    deposit_amount: Optional[Decimal] = Field(default=None)
    currency: Optional[str] = Field(default=None)
    cancelled_at: Optional[datetime] = Field(default=None)
    cancel_reason: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    created_by_id: Optional[UUID] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    rooms: list[BookingRoomLineResult] = Field(default_factory=list)
    slots: list[BookingSlotResult] = Field(default_factory=list)


class BookingPageResult(BaseModel):
    """Paginated bookings."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[BookingListItemResult] = Field(default_factory=list)


class BookingRangeResult(BaseModel):
    """Complete booking set for a Calendar/Grid time window."""

    items: list[BookingListItemResult] = Field(default_factory=list)


class OverrideLogResult(UUIDBaseModel):
    """Override audit log row."""

    facility_booking_id: UUID = Field(...)
    overridden_booking_id: Optional[UUID] = Field(default=None)
    overridden_by_id: UUID = Field(...)
    overridden_by_name: Optional[str] = Field(default=None)
    facility_id: UUID = Field(...)
    facility_name: Optional[str] = Field(default=None)
    outcome: str = Field(...)
    reason: Optional[str] = Field(default=None)
    created_at: datetime = Field(...)
    created_by: Optional[str] = Field(default=None)


class OverrideLogPageResult(BaseModel):
    """Paginated override logs."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[OverrideLogResult] = Field(default_factory=list)


class TimeSlotResult(BaseModel):
    """Available time window."""

    start: str = Field(..., description="HH:MM local")
    end: str = Field(..., description="HH:MM local")


class DayAvailabilityResult(BaseModel):
    """AM/PM availability buckets."""

    am: list[TimeSlotResult] = Field(default_factory=list)
    pm: list[TimeSlotResult] = Field(default_factory=list)


class RoomAvailabilityResult(UUIDBaseModel):
    """Room with day availability."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)
    photo_urls: list[str] = Field(default_factory=list)
    availability: DayAvailabilityResult = Field(default_factory=DayAvailabilityResult)


class RoomAvailabilityListResult(BaseModel):
    """Rooms available on a date."""

    date: DateType = Field(...)
    items: list[RoomAvailabilityResult] = Field(default_factory=list)
