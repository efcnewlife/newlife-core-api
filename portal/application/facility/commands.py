"""
Facility booking application commands.
"""
from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand, PagesQueryCommand
from portal.domain.facility.constants import BookingType, RentalRateBillingUnit

# Ministry commands live in org.
from portal.application.org.commands import (
    CreateMinistryCommand,
    MinistryMemberEntryCommand,
    ReplaceMinistryMembersCommand,
    UpdateMinistryCommand,
)


class FacilityTranslationCommand(BaseModel):
    """Localized facility content."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class CreateRoomCommand(BaseModel):
    """Create facility room."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: list[FacilityTranslationCommand] = Field(..., min_length=1)


class UpdateRoomCommand(BaseModel):
    """Update facility room (code is immutable)."""

    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None)
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: Optional[list[FacilityTranslationCommand]] = Field(default=None)


class CreateRoomSlotTemplateCommand(BaseModel):
    """Create room slot template."""

    facility_id: UUID = Field(...)
    name: str = Field(...)
    days_of_week: list[int] = Field(...)
    start_time: time = Field(...)
    end_time: time = Field(...)
    slot_duration_minutes: int = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)


class UpdateRoomSlotTemplateCommand(BaseModel):
    """Update room slot template."""

    facility_id: UUID = Field(...)
    name: str = Field(...)
    days_of_week: list[int] = Field(...)
    start_time: time = Field(...)
    end_time: time = Field(...)
    slot_duration_minutes: int = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)


class CreateRentalRateCommand(BaseModel):
    """Create rental rate row."""

    facility_id: UUID = Field(...)
    billing_unit: RentalRateBillingUnit = Field(default=RentalRateBillingUnit.HOURLY)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)
    sequence: Optional[float] = Field(default=None)
    translations: list[FacilityTranslationCommand] = Field(..., min_length=1)


class UpdateRentalRateCommand(BaseModel):
    """Update rental rate row."""

    facility_id: UUID = Field(...)
    billing_unit: RentalRateBillingUnit = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)
    sequence: Optional[float] = Field(default=None)
    translations: Optional[list[FacilityTranslationCommand]] = Field(default=None)
    name: Optional[str] = Field(default=None)


class CreateDiscountRuleCommand(BaseModel):
    """Create rental discount rule."""

    code: str = Field(...)
    percent_off: Decimal = Field(...)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)


class UpdateDiscountRuleCommand(BaseModel):
    """Update rental discount rule."""

    code: str = Field(...)
    percent_off: Decimal = Field(...)
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None)


class CreateSurchargeCommand(BaseModel):
    """Create rental surcharge."""

    code: str = Field(...)
    charge_type: str = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_active: bool = Field(default=True)
    applies_to_booking_type: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class UpdateSurchargeCommand(BaseModel):
    """Update rental surcharge."""

    code: str = Field(...)
    charge_type: str = Field(...)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_active: bool = Field(default=True)
    applies_to_booking_type: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class UpdatePolicySettingCommand(BaseModel):
    """Update rental policy setting."""

    amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_active: bool = Field(default=True)


class PreviewQuoteRoomLineCommand(BaseModel):
    """Room line for quote preview."""

    facility_id: UUID = Field(...)
    billed_hours: Decimal = Field(...)


class PreviewQuoteCommand(BaseModel):
    """Preview rental quote."""

    booking_type: BookingType = Field(...)
    is_mission_aligned: bool = Field(default=False)
    currency: str = Field(default="CAD")
    as_of_date: Optional[date] = Field(default=None)
    room_lines: list[PreviewQuoteRoomLineCommand] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)


class BookingPagesQueryCommand(PagesQueryCommand):
    """Paginated booking list filters."""

    facility_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    status: Optional[str] = Field(default=None)
    booking_type: Optional[str] = Field(default=None)
    date_from: Optional[datetime] = Field(default=None)
    date_to: Optional[datetime] = Field(default=None)


class MemberPagesQueryCommand(PagesQueryCommand):
    """Paginated facility member list filters."""

    ministry_id: Optional[UUID] = Field(default=None)


class MinistryMemberPagesQueryCommand(PagesQueryCommand):
    """Paginated ministry member assignment list."""

    ministry_id: Optional[UUID] = Field(default=None)


class OverrideLogPagesQueryCommand(PagesQueryCommand):
    """Paginated override audit log filters."""

    facility_id: Optional[UUID] = Field(default=None)
    overridden_by_id: Optional[UUID] = Field(default=None)
    date_from: Optional[datetime] = Field(default=None)
    date_to: Optional[datetime] = Field(default=None)


class BookingRoomLineCommand(BaseModel):
    """Room line on booking update."""

    facility_id: UUID = Field(...)
    start_at: Optional[datetime] = Field(default=None)
    end_at: Optional[datetime] = Field(default=None)
    sequence: int = Field(default=0)


class UpdateBookingCommand(BaseModel):
    """Admin update booking times/rooms."""

    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    rooms: list[BookingRoomLineCommand] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)


class CancelBookingCommand(BaseModel):
    """Cancel booking."""

    scope: str = Field(default="single")
    cancel_reason: Optional[str] = Field(default=None)


class ReplaceMinistryMemberCommand(BaseModel):
    """Replace ministry memberships for a user."""

    ministry_ids: list[UUID] = Field(default_factory=list)


__all__ = [
    "ReplaceMinistryMembersCommand",
    "BookingPagesQueryCommand",
    "BookingRoomLineCommand",
    "BulkIdsCommand",
    "CancelBookingCommand",
    "CreateDiscountRuleCommand",
    "CreateMinistryCommand",
    "CreateRentalRateCommand",
    "CreateRoomCommand",
    "CreateRoomSlotTemplateCommand",
    "CreateSurchargeCommand",
    "DeleteCommand",
    "FacilityTranslationCommand",
    "MemberPagesQueryCommand",
    "MinistryMemberPagesQueryCommand",
    "OverrideLogPagesQueryCommand",
    "PagesQueryCommand",
    "PreviewQuoteCommand",
    "PreviewQuoteRoomLineCommand",
    "ReplaceMinistryMemberCommand",
    "UpdateBookingCommand",
    "UpdateDiscountRuleCommand",
    "UpdateMinistryCommand",
    "UpdatePolicySettingCommand",
    "UpdateRentalRateCommand",
    "UpdateRoomCommand",
    "UpdateRoomSlotTemplateCommand",
    "UpdateSurchargeCommand",
]
