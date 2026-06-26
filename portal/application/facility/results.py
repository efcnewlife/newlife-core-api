"""
Facility booking application results.
"""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.common.mixins import JsonStringParseModel, UUIDBaseModel
from portal.domain.facility.constants import RentalRateBillingUnit

from portal.application.org.results import (
    CreateIdResult,
    MinistryDetailResult,
    MinistryListItemResult,
    MinistryListResult,
    MinistryPageResult,
    TranslationItemResult,
)


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
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)
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


class RentalRateResult(UUIDBaseModel):
    """Rental rate row."""

    facility_id: UUID = Field(...)
    billing_unit: str = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(...)
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)
    sequence: Optional[float] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    translations: list[TranslationItemResult] = Field(default_factory=list)


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
    """Quoted room line."""

    facility_id: UUID = Field(...)
    billed_hours: Decimal = Field(...)
    pricing_tier_used: str = Field(...)
    rental_rate_id: Optional[UUID] = Field(default=None)
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
    """Booking room line detail."""

    facility_id: UUID = Field(...)
    facility_name: Optional[str] = Field(default=None)
    facility_code: Optional[str] = Field(default=None)
    sequence: int = Field(default=0)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    billed_hours: Optional[Decimal] = Field(default=None)
    pricing_tier_used: Optional[str] = Field(default=None)
    rental_rate_id: Optional[UUID] = Field(default=None)
    line_subtotal: Optional[Decimal] = Field(default=None)


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
    recurrence_rule: Optional[str] = Field(
        default=None,
        description="iCal RRULE string (RFC 5545); series anchor is start_at",
    )
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
    rooms: list[BookingRoomLineResult] = Field(default_factory=list)
    slots: list[BookingSlotResult] = Field(default_factory=list)


class BookingPageResult(BaseModel):
    """Paginated bookings."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[BookingListItemResult] = Field(default_factory=list)


class MemberMinistryTagResult(UUIDBaseModel):
    """Ministry tag on member row."""

    name: Optional[str] = Field(default=None)


class MemberListItemResult(UUIDBaseModel):
    """Facility member list row."""

    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)
    ministries: list[MemberMinistryTagResult] = Field(default_factory=list)


class MemberPageResult(BaseModel):
    """Paginated facility members."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[MemberListItemResult] = Field(default_factory=list)


class MemberDetailResult(UUIDBaseModel):
    """Facility member detail."""

    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)
    last_login_at: Optional[datetime] = Field(default=None)
    ministries: list[MemberMinistryTagResult] = Field(default_factory=list)


class MinistryMemberRowResult(BaseModel):
    """Ministry member assignment row."""

    user_id: UUID = Field(...)
    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)
    ministry_ids: list[UUID] = Field(default_factory=list)
    ministry_names: list[str] = Field(default_factory=list)


class MinistryMemberPageResult(BaseModel):
    """Paginated ministry members."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[MinistryMemberRowResult] = Field(default_factory=list)


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
