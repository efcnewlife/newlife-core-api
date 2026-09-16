"""
Admin Recurring Booking Series serializers.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRecurringBookingSeriesRoomInput(BaseModel):
    """Room on a Recurring Booking Series; all rooms share the Series time window."""

    facility_id: UUID = Field(...)
    sequence: int = Field(default=0)


class AdminRecurringBookingSeriesCreate(BaseModel):
    """Admin create Recurring Booking Series on behalf of a Booker."""

    user_id: UUID = Field(..., description="Booker user id")
    ministry_id: Optional[UUID] = Field(default=None)
    first_occurrence_date: date = Field(...)
    last_occurrence_date: date = Field(...)
    local_start_time: time = Field(...)
    local_end_time: time = Field(...)
    is_mission_aligned: bool = Field(default=False)
    rooms: list[AdminRecurringBookingSeriesRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)


class AdminRecurringBookingOccurrence(UUIDBaseModel):
    """Materialized Booking Occurrence on a Recurring Booking Series."""

    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    facility_ids: list[UUID] = Field(default_factory=list, serialization_alias="facilityIds")


class AdminRecurringBookingSeriesDetail(UUIDBaseModel):
    """Created Recurring Booking Series with occurrences."""

    user_id: UUID = Field(..., serialization_alias="userId")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    first_occurrence_date: date = Field(..., serialization_alias="firstOccurrenceDate")
    last_occurrence_date: date = Field(..., serialization_alias="lastOccurrenceDate")
    local_start_time: time = Field(..., serialization_alias="localStartTime")
    local_end_time: time = Field(..., serialization_alias="localEndTime")
    status: str = Field(...)
    payment_hold_expires_at: datetime = Field(..., serialization_alias="paymentHoldExpiresAt")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    occurrence_count: int = Field(..., serialization_alias="occurrenceCount")
    is_priority: bool = Field(default=False, serialization_alias="isPriority")
    occurrences: list[AdminRecurringBookingOccurrence] = Field(default_factory=list)
