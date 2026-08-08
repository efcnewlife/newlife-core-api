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


class CreateRoomBlackoutCommand(BaseModel):
    """Create room blackout."""

    facility_id: Optional[UUID] = Field(default=None)
    name: str = Field(...)
    reason: str = Field(...)
    kind: str = Field(...)
    blackout_date: Optional[date] = Field(default=None)
    days_of_week: Optional[list[int]] = Field(default=None)
    start_time: time = Field(...)
    end_time: time = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)


class UpdateRoomBlackoutCommand(BaseModel):
    """Update room blackout."""

    facility_id: Optional[UUID] = Field(default=None)
    name: str = Field(...)
    reason: str = Field(...)
    kind: str = Field(...)
    blackout_date: Optional[date] = Field(default=None)
    days_of_week: Optional[list[int]] = Field(default=None)
    start_time: time = Field(...)
    end_time: time = Field(...)
    is_active: bool = Field(default=True)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)


class CreateRentalRateTemplateCommand(BaseModel):
    """Create rental rate template."""

    name: str = Field(...)
    billing_unit: RentalRateBillingUnit = Field(default=RentalRateBillingUnit.HOURLY)
    applicability: Optional[dict] = Field(default=None)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)


class UpdateRentalRateTemplateCommand(BaseModel):
    """Update rental rate template."""

    name: str = Field(...)
    billing_unit: RentalRateBillingUnit = Field(...)
    applicability: Optional[dict] = Field(default=None)
    unit_amount: Decimal = Field(...)
    currency: str = Field(default="CAD")
    is_default: bool = Field(default=False)
    is_active: bool = Field(default=True)


class CreateRentalRateCommand(BaseModel):
    """Create room binding to a rate template."""

    facility_id: UUID = Field(...)
    template_id: UUID = Field(...)
    is_active: bool = Field(default=True)


class UpdateRentalRateCommand(BaseModel):
    """Update room binding to a rate template."""

    facility_id: UUID = Field(...)
    template_id: UUID = Field(...)
    is_active: bool = Field(default=True)


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


class CreateBookingCommand(BaseModel):
    """Create a one-time booking."""

    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None, description="Booker; omit to use UserContext")
    rooms: list[BookingRoomLineCommand] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)


class RoomAvailabilityQueryCommand(BaseModel):
    """Query room availability for a date."""

    target_date: date = Field(...)
    ministry_id: Optional[UUID] = Field(default=None)


__all__ = [
    "ReplaceMinistryMembersCommand",
    "BookingPagesQueryCommand",
    "BookingRoomLineCommand",
    "BulkIdsCommand",
    "CancelBookingCommand",
    "CreateBookingCommand",
    "CreateDiscountRuleCommand",
    "CreateMinistryCommand",
    "CreateRentalRateCommand",
    "CreateRentalRateTemplateCommand",
    "CreateRoomCommand",
    "CreateRoomBlackoutCommand",
    "CreateRoomSlotTemplateCommand",
    "CreateSurchargeCommand",
    "DeleteCommand",
    "FacilityTranslationCommand",
    "OverrideLogPagesQueryCommand",
    "PagesQueryCommand",
    "PreviewQuoteCommand",
    "PreviewQuoteRoomLineCommand",
    "RoomAvailabilityQueryCommand",
    "UpdateBookingCommand",
    "UpdateDiscountRuleCommand",
    "UpdateMinistryCommand",
    "UpdatePolicySettingCommand",
    "UpdateRentalRateCommand",
    "UpdateRentalRateTemplateCommand",
    "UpdateRoomBlackoutCommand",
    "UpdateRoomCommand",
    "UpdateRoomSlotTemplateCommand",
    "UpdateSurchargeCommand",
]
