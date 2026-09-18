"""
Admin Recurring Booking Series serializers.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.facility.booking_title import BookingTitle
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRecurringBookingSeriesRoomInput(BaseModel):
    """Room on a Recurring Booking Series; all rooms share the Series time window."""

    facility_id: UUID = Field(...)
    sequence: int = Field(default=0)


class AdminRecurringBookingSeriesProposal(BaseModel):
    """Proposed Recurring Booking Series for conflict preview."""

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


class AdminRecurringBookingSeriesCreate(AdminRecurringBookingSeriesProposal):
    """Admin create Recurring Booking Series on behalf of a Booker."""

    title: BookingTitle = Field(...)
    excluded_dates: list[date] = Field(default_factory=list)


class AdminRecurringBookingSeriesCancel(BaseModel):
    """Cancel Recurring Booking Series occurrences by scope."""

    scope: str = Field(...)
    occurrence_id: Optional[UUID] = Field(default=None)
    cancel_reason: Optional[str] = Field(default=None)


class AdminRecurringBookingOccurrence(UUIDBaseModel):
    """Materialized Booking Occurrence on a Recurring Booking Series."""

    title: str = Field(default="")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    facility_ids: list[UUID] = Field(default_factory=list, serialization_alias="facilityIds")


class AdminRecurringBookingSeriesDetail(UUIDBaseModel):
    """Created Recurring Booking Series with occurrences."""

    title: str = Field(default="")
    user_id: UUID = Field(..., serialization_alias="userId")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_name: Optional[str] = Field(default=None, serialization_alias="ministryName")
    first_occurrence_date: date = Field(..., serialization_alias="firstOccurrenceDate")
    last_occurrence_date: date = Field(..., serialization_alias="lastOccurrenceDate")
    local_start_time: time = Field(..., serialization_alias="localStartTime")
    local_end_time: time = Field(..., serialization_alias="localEndTime")
    status: str = Field(...)
    payment_hold_expires_at: Optional[datetime] = Field(default=None, serialization_alias="paymentHoldExpiresAt")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    occurrence_count: int = Field(..., serialization_alias="occurrenceCount")
    is_priority: bool = Field(default=False, serialization_alias="isPriority")
    confirmed_by_id: Optional[UUID] = Field(default=None, serialization_alias="confirmedById")
    occurrences: list[AdminRecurringBookingOccurrence] = Field(default_factory=list)


class AdminRecurringBookingConflict(BaseModel):
    """One unavailable occurrence in a Recurring Booking conflict preview."""

    occurrence_date: date = Field(..., serialization_alias="occurrenceDate")
    kind: str = Field(...)
    facility_ids: list[UUID] = Field(default_factory=list, serialization_alias="facilityIds")
    is_overridable: bool = Field(default=False, serialization_alias="isOverridable")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_steward_display_name: Optional[str] = Field(default=None, serialization_alias="ministryStewardDisplayName")
    ministry_steward_email: Optional[str] = Field(default=None, serialization_alias="ministryStewardEmail")


class AdminRecurringBookingPreview(BaseModel):
    """Recurring Booking conflict preview; does not persist a Series."""

    conflicts: list[AdminRecurringBookingConflict] = Field(default_factory=list)


class AdminPendingPaymentSeriesItem(UUIDBaseModel):
    """Pending-payment Recurring Booking Series row for payment confirmation."""

    user_id: UUID = Field(..., serialization_alias="userId")
    user_email: Optional[str] = Field(default=None, serialization_alias="userEmail")
    user_display_name: Optional[str] = Field(default=None, serialization_alias="userDisplayName")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_name: Optional[str] = Field(default=None, serialization_alias="ministryName")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    occurrence_count: int = Field(..., serialization_alias="occurrenceCount")
    payment_hold_expires_at: Optional[datetime] = Field(default=None, serialization_alias="paymentHoldExpiresAt")
    is_priority: bool = Field(default=False, serialization_alias="isPriority")


class AdminPendingPaymentSeriesList(BaseModel):
    """Actionable Pending-payment Recurring Booking Series."""

    items: list[AdminPendingPaymentSeriesItem] = Field(default_factory=list)
