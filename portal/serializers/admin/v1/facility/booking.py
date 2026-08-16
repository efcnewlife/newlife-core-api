"""
Admin facility booking serializers.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminBookingQuery(GenericQueryBaseModel):
    """Booking list filters."""

    facility_id: Optional[UUID] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    status: Optional[str] = Field(default=None)
    booking_type: Optional[str] = Field(default=None)
    date_from: Optional[datetime] = Field(default=None)
    date_to: Optional[datetime] = Field(default=None)


class AdminBookingRoomLine(UUIDBaseModel):
    """Booking room line with rule snapshot."""

    facility_id: UUID = Field(..., serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    facility_code: Optional[str] = Field(default=None, serialization_alias="facilityCode")
    sequence: int = Field(default=0)
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    billed_hours: Optional[Decimal] = Field(default=None, serialization_alias="billedHours")
    rental_rate_name: Optional[str] = Field(default=None, serialization_alias="rentalRateName")
    billing_unit: Optional[str] = Field(default=None, serialization_alias="billingUnit")
    unit_amount: Optional[Decimal] = Field(default=None, serialization_alias="unitAmount")
    currency: Optional[str] = Field(default=None)
    applicability: Optional[dict] = Field(default=None)
    is_default: Optional[bool] = Field(default=None, serialization_alias="isDefault")
    line_subtotal: Optional[Decimal] = Field(default=None, serialization_alias="lineSubtotal")


class AdminBookingSlot(UUIDBaseModel):
    """Booking slot row."""

    facility_id: UUID = Field(..., serialization_alias="facilityId")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)


class AdminBookingListItem(UUIDBaseModel):
    """Booking list row."""

    user_id: UUID = Field(..., serialization_alias="userId")
    user_email: Optional[str] = Field(default=None, serialization_alias="userEmail")
    user_display_name: Optional[str] = Field(default=None, serialization_alias="userDisplayName")
    facility_id: Optional[UUID] = Field(default=None, serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    facility_names: list[str] = Field(default_factory=list, serialization_alias="facilityNames")
    booking_type: str = Field(..., serialization_alias="bookingType")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)
    quoted_amount: Optional[Decimal] = Field(default=None, serialization_alias="quotedAmount")
    currency: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt")


class AdminBookingPages(PaginationBaseResponseModel):
    """Paginated bookings."""

    items: list[AdminBookingListItem] = Field(default_factory=list)


class AdminBookingDetail(AdminBookingListItem):
    """Booking detail."""

    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    recurrence_rule: Optional[str] = Field(
        default=None, serialization_alias="recurrenceRule", description="iCal RRULE string (RFC 5545); series anchor is start_at"
    )
    recurrence_end_at: Optional[datetime] = Field(default=None, serialization_alias="recurrenceEndAt", description="Recurrence series end")
    is_mission_aligned: bool = Field(default=False, serialization_alias="isMissionAligned")
    subtotal_amount: Optional[Decimal] = Field(default=None, serialization_alias="subtotalAmount")
    discount_percent: Optional[Decimal] = Field(default=None, serialization_alias="discountPercent")
    discount_amount: Optional[Decimal] = Field(default=None, serialization_alias="discountAmount")
    surcharge_amount: Optional[Decimal] = Field(default=None, serialization_alias="surchargeAmount")
    deposit_amount: Optional[Decimal] = Field(default=None, serialization_alias="depositAmount")
    cancelled_at: Optional[datetime] = Field(default=None, serialization_alias="cancelledAt")
    cancel_reason: Optional[str] = Field(default=None, serialization_alias="cancelReason")
    remark: Optional[str] = Field(default=None)
    created_by_id: Optional[UUID] = Field(default=None, serialization_alias="createdById")
    created_by: Optional[str] = Field(default=None, serialization_alias="createdBy")
    rooms: list[AdminBookingRoomLine] = Field(default_factory=list)
    slots: list[AdminBookingSlot] = Field(default_factory=list)


class AdminBookingRoomInput(BaseModel):
    """Room line for booking update/create."""

    facility_id: UUID = Field(...)
    start_at: Optional[datetime] = Field(default=None)
    end_at: Optional[datetime] = Field(default=None)
    sequence: int = Field(default=0)


class AdminBookingCreate(BaseModel):
    """Admin create booking on behalf of a Booker."""

    user_id: UUID = Field(..., description="Booker user id")
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    rooms: list[AdminBookingRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)


class AdminBookingUpdate(BaseModel):
    """Update booking."""

    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    rooms: list[AdminBookingRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)


class AdminBookingCancel(BaseModel):
    """Cancel booking."""

    scope: str = Field(default="single")
    cancel_reason: Optional[str] = Field(default=None)
