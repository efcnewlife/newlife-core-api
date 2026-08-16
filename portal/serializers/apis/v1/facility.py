"""
Member facility API serializers.
"""

from datetime import date as DateType
from datetime import datetime
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
