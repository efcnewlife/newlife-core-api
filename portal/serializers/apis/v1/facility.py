"""
Member facility API serializers.
"""

from datetime import date as DateType
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class MemberTimeSlot(BaseModel):
    """Available time window."""

    start: str = Field(..., description="HH:MM")
    end: str = Field(..., description="HH:MM")


class MemberDayAvailability(BaseModel):
    """AM/PM availability."""

    am: list[MemberTimeSlot] = Field(default_factory=list)
    pm: list[MemberTimeSlot] = Field(default_factory=list)


class MemberRoomAvailabilityItem(UUIDBaseModel):
    """Room with availability for a date."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)
    room_number: Optional[str] = Field(default=None, serialization_alias="roomNumber")
    capacity: Optional[int] = Field(default=None)
    is_active: bool = Field(default=True, serialization_alias="isActive")
    photo_urls: list[str] = Field(default_factory=list, serialization_alias="photoUrls")
    availability: MemberDayAvailability = Field(default_factory=MemberDayAvailability)


class MemberRoomAvailabilityList(BaseModel):
    """Availability response."""

    date: DateType = Field(...)
    items: list[MemberRoomAvailabilityItem] = Field(default_factory=list)


class MemberBookingRoomInput(BaseModel):
    """Room line for create booking."""

    facility_id: UUID = Field(...)
    start_at: Optional[datetime] = Field(default=None)
    end_at: Optional[datetime] = Field(default=None)
    sequence: int = Field(default=0)


class MemberBookingCreate(BaseModel):
    """Create booking request."""

    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    rooms: list[MemberBookingRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)


class MemberBookingCancel(BaseModel):
    """Cancel booking request."""

    scope: str = Field(default="single")
    cancel_reason: Optional[str] = Field(default=None)


class MemberBookingListItem(UUIDBaseModel):
    """Member booking list row."""

    facility_id: Optional[UUID] = Field(default=None, serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    booking_type: str = Field(..., serialization_alias="bookingType")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)
    quoted_amount: Optional[str] = Field(default=None, serialization_alias="quotedAmount")
    currency: Optional[str] = Field(default=None)


class MemberBookingList(BaseModel):
    """Member bookings."""

    items: list[MemberBookingListItem] = Field(default_factory=list)


class MemberPreviewQuoteRoomInput(BaseModel):
    """Room line for member preview quote."""

    facility_id: UUID = Field(...)


class MemberPreviewQuoteRequest(BaseModel):
    """Preview quote for a One-time interval and room list."""

    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    currency: str = Field(default="CAD")
    surcharge_codes: list[str] = Field(default_factory=list)
    rooms: list[MemberPreviewQuoteRoomInput] = Field(min_length=1)


class MemberPreviewQuoteRoomLineResult(BaseModel):
    """Quoted room line."""

    facility_id: UUID = Field(..., serialization_alias="facilityId")
    billed_hours: Decimal = Field(..., serialization_alias="billedHours")
    rental_rate_name: str = Field(..., serialization_alias="rentalRateName")
    billing_unit: str = Field(..., serialization_alias="billingUnit")
    unit_amount: Decimal = Field(..., serialization_alias="unitAmount")
    currency: str = Field(...)
    applicability: Optional[dict] = Field(default=None)
    is_default: bool = Field(default=False, serialization_alias="isDefault")
    line_subtotal: Decimal = Field(..., serialization_alias="lineSubtotal")


class MemberPreviewQuoteResponse(BaseModel):
    """Member preview quote totals."""

    subtotal_amount: Decimal = Field(..., serialization_alias="subtotalAmount")
    discount_percent: Decimal = Field(..., serialization_alias="discountPercent")
    discount_amount: Decimal = Field(..., serialization_alias="discountAmount")
    surcharge_amount: Decimal = Field(..., serialization_alias="surchargeAmount")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    room_lines: list[MemberPreviewQuoteRoomLineResult] = Field(default_factory=list, serialization_alias="roomLines")
