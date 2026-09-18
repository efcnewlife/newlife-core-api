"""
Member facility API serializers.
"""

from datetime import date as DateType
from datetime import datetime, time
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.facility.booking_title import BookingTitle
from portal.domain.facility.cancellation_reason import MemberCancellationReason
from portal.domain.facility.constants import PREVIEW_QUOTE_MAX_LINES, MyBookingsSection
from portal.serializers.mixins.base import PaginationBaseResponseModel
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
    max_booking_lines: int = Field(..., serialization_alias="maxBookingLines")


class MemberBookingRoomInput(BaseModel):
    """Room line for create booking."""

    facility_id: UUID = Field(...)
    start_at: Optional[datetime] = Field(default=None)
    end_at: Optional[datetime] = Field(default=None)
    sequence: int = Field(default=0)


class MemberBookingCreate(BaseModel):
    """Create booking request."""

    title: BookingTitle = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    rooms: list[MemberBookingRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)
    booking_draft_id: Optional[UUID] = Field(default=None, description="Source Booking Draft; deleted on successful create")


class MemberBookingCancel(BaseModel):
    """Cancel booking request."""

    scope: str = Field(default="single")
    cancel_reason: MemberCancellationReason = Field(...)


class MemberBookingTitleUpdate(BaseModel):
    """Booker-only Booking title update."""

    title: BookingTitle = Field(...)


class MemberBookingListItem(UUIDBaseModel):
    """Member booking list row."""

    title: str = Field(default="")
    facility_id: Optional[UUID] = Field(default=None, serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    booking_type: str = Field(..., serialization_alias="bookingType")
    series_id: Optional[UUID] = Field(default=None, serialization_alias="seriesId")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    status: str = Field(...)
    quoted_amount: Optional[str] = Field(default=None, serialization_alias="quotedAmount")
    currency: Optional[str] = Field(default=None)


class MemberBookingBrowseQuery(BaseModel):
    """Participant-scoped My Bookings browse query."""

    section: MyBookingsSection = Field(...)
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=20, ge=1, le=50)


class MemberBookingBrowseCard(BaseModel):
    """One-time Booking or Recurring Booking Series projection for one section."""

    kind: str = Field(...)
    is_booker: bool = Field(..., serialization_alias="isBooker")
    is_view_only: bool = Field(..., serialization_alias="isViewOnly")
    photo_urls: list[str] = Field(default_factory=list, serialization_alias="photoUrls")
    booking: Optional[MemberBookingListItem] = Field(default=None)
    series_id: Optional[UUID] = Field(default=None, serialization_alias="seriesId")
    series_title: Optional[str] = Field(default=None, serialization_alias="seriesTitle")
    occurrences: list[MemberBookingListItem] = Field(default_factory=list)


class MemberBookingBrowsePage(PaginationBaseResponseModel):
    """Paginated My Bookings browse page."""

    section: str = Field(...)
    items: list[MemberBookingBrowseCard] = Field(default_factory=list)


class MemberBookingDetailRoom(UUIDBaseModel):
    """Room line on member booking detail."""

    facility_id: UUID = Field(..., serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    sequence: int = Field(default=0)
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    billed_hours: Optional[Decimal] = Field(default=None, serialization_alias="billedHours")
    rental_rate_name: Optional[str] = Field(default=None, serialization_alias="rentalRateName")
    billing_unit: Optional[str] = Field(default=None, serialization_alias="billingUnit")
    unit_amount: Optional[Decimal] = Field(default=None, serialization_alias="unitAmount")
    currency: Optional[str] = Field(default=None)
    line_subtotal: Optional[Decimal] = Field(default=None, serialization_alias="lineSubtotal")
    photo_urls: list[str] = Field(default_factory=list, serialization_alias="photoUrls")


class MemberBookingTimelineEvent(BaseModel):
    """Member-visible lifecycle timeline entry."""

    kind: str = Field(...)
    occurred_at: datetime = Field(..., serialization_alias="occurredAt")
    reason: Optional[str] = Field(default=None)


class MemberBookingActions(BaseModel):
    """Booker-only self-service eligibility."""

    can_edit_title: bool = Field(..., serialization_alias="canEditTitle")
    can_cancel: bool = Field(..., serialization_alias="canCancel")
    can_view_payment_instructions: bool = Field(..., serialization_alias="canViewPaymentInstructions")
    can_book_again: bool = Field(..., serialization_alias="canBookAgain")
    book_again_date: Optional[DateType] = Field(default=None, serialization_alias="bookAgainDate")


class MemberBookingDetail(UUIDBaseModel):
    """Participant-authorized Booking or Occurrence detail."""

    title: str = Field(default="")
    status: str = Field(...)
    booking_type: str = Field(default="", serialization_alias="bookingType")
    series_id: Optional[UUID] = Field(default=None, serialization_alias="seriesId")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_name: Optional[str] = Field(default=None, serialization_alias="ministryName")
    remark: Optional[str] = Field(default=None)
    booker_display_name: Optional[str] = Field(default=None, serialization_alias="bookerDisplayName")
    booker_email: Optional[str] = Field(default=None, serialization_alias="bookerEmail")
    quoted_amount: Optional[Decimal] = Field(default=None, serialization_alias="quotedAmount")
    subtotal_amount: Optional[Decimal] = Field(default=None, serialization_alias="subtotalAmount")
    discount_percent: Optional[Decimal] = Field(default=None, serialization_alias="discountPercent")
    discount_amount: Optional[Decimal] = Field(default=None, serialization_alias="discountAmount")
    surcharge_amount: Optional[Decimal] = Field(default=None, serialization_alias="surchargeAmount")
    currency: Optional[str] = Field(default=None)
    payment_hold_expires_at: Optional[datetime] = Field(default=None, serialization_alias="paymentHoldExpiresAt")
    is_booker: bool = Field(default=False, serialization_alias="isBooker")
    is_view_only: bool = Field(default=True, serialization_alias="isViewOnly")
    rooms: list[MemberBookingDetailRoom] = Field(default_factory=list)
    timeline: list[MemberBookingTimelineEvent] = Field(default_factory=list)
    actions: MemberBookingActions = Field(
        default_factory=lambda: MemberBookingActions(can_edit_title=False, can_cancel=False, can_view_payment_instructions=False, can_book_again=False)
    )


class MemberPreviewQuoteLineInput(BaseModel):
    """Booking line for member preview quote."""

    facility_id: UUID = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)


class MemberPreviewQuoteRequest(BaseModel):
    """Preview quote for One-time booking lines (each with its own interval)."""

    is_mission_aligned: bool = Field(default=False)
    ministry_id: Optional[UUID] = Field(default=None)
    currency: str = Field(default="CAD")
    surcharge_codes: list[str] = Field(default_factory=list)
    lines: list[MemberPreviewQuoteLineInput] = Field(min_length=1, max_length=PREVIEW_QUOTE_MAX_LINES)


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


class MemberBookingDraftLineInput(BaseModel):
    """Line for create Booking Draft."""

    facility_id: UUID = Field(...)
    start_at: datetime = Field(...)
    end_at: datetime = Field(...)
    sequence: int = Field(default=0)


class MemberBookingDraftCreate(BaseModel):
    """Create Booking Draft request."""

    ministry_id: Optional[UUID] = Field(default=None)
    lines: list[MemberBookingDraftLineInput] = Field(default_factory=list)


class MemberBookingDraftUpdate(BaseModel):
    """Replace a Booking Draft's lines in place (PATCH; last-write-wins)."""

    ministry_id: Optional[UUID] = Field(default=None)
    lines: list[MemberBookingDraftLineInput] = Field(default_factory=list)


class MemberBookingDraftLine(BaseModel):
    """Booking Draft line with live availability."""

    facility_id: UUID = Field(..., serialization_alias="facilityId")
    start_at: datetime = Field(..., serialization_alias="startAt")
    end_at: datetime = Field(..., serialization_alias="endAt")
    sequence: int = Field(default=0)
    is_available: bool = Field(..., serialization_alias="isAvailable")


class MemberBookingDraftDetail(UUIDBaseModel):
    """Booking Draft detail: lines plus freshly computed price and availability."""

    date: DateType = Field(...)
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    lines: list[MemberBookingDraftLine] = Field(default_factory=list)
    subtotal_amount: Decimal = Field(..., serialization_alias="subtotalAmount")
    discount_percent: Decimal = Field(..., serialization_alias="discountPercent")
    discount_amount: Decimal = Field(..., serialization_alias="discountAmount")
    surcharge_amount: Decimal = Field(..., serialization_alias="surchargeAmount")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)


class MemberRecurringBookingSeriesRoomInput(BaseModel):
    """Room on a Recurring Booking Series; all rooms share the Series time window."""

    facility_id: UUID = Field(...)
    sequence: int = Field(default=0)


class MemberRecurringBookingSeriesProposal(BaseModel):
    """Proposed Recurring Booking Series for conflict preview."""

    ministry_id: Optional[UUID] = Field(default=None)
    first_occurrence_date: DateType = Field(...)
    last_occurrence_date: DateType = Field(...)
    local_start_time: time = Field(...)
    local_end_time: time = Field(...)
    is_mission_aligned: bool = Field(default=False)
    rooms: list[MemberRecurringBookingSeriesRoomInput] = Field(default_factory=list)
    surcharge_codes: list[str] = Field(default_factory=list)
    remark: Optional[str] = Field(default=None)


class MemberRecurringBookingSeriesCreate(MemberRecurringBookingSeriesProposal):
    """Create a weekly Recurring Booking Series."""

    title: BookingTitle = Field(...)
    excluded_dates: list[DateType] = Field(default_factory=list)


class MemberRecurringBookingSeriesTitleUpdate(BaseModel):
    """Booker-only Recurring Booking Series title update."""

    title: BookingTitle = Field(...)


class MemberRecurringBookingSeriesCancel(BaseModel):
    """Cancel Recurring Booking Series occurrences by scope."""

    scope: str = Field(...)
    occurrence_id: Optional[UUID] = Field(default=None)
    cancel_reason: MemberCancellationReason = Field(...)


class MemberRecurringBookingOccurrence(MemberBookingDetail):
    """Materialized Booking Occurrence on a Recurring Booking Series."""


class MemberRecurringBookingSeriesDetail(UUIDBaseModel):
    """Created Recurring Booking Series with occurrences."""

    title: str = Field(default="")
    user_id: Optional[UUID] = Field(default=None, serialization_alias="userId")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_name: Optional[str] = Field(default=None, serialization_alias="ministryName")
    remark: Optional[str] = Field(default=None)
    first_occurrence_date: DateType = Field(..., serialization_alias="firstOccurrenceDate")
    last_occurrence_date: DateType = Field(..., serialization_alias="lastOccurrenceDate")
    local_start_time: time = Field(..., serialization_alias="localStartTime")
    local_end_time: time = Field(..., serialization_alias="localEndTime")
    status: str = Field(...)
    payment_hold_expires_at: Optional[datetime] = Field(default=None, serialization_alias="paymentHoldExpiresAt")
    quoted_amount: Decimal = Field(..., serialization_alias="quotedAmount")
    currency: str = Field(...)
    occurrence_count: int = Field(..., serialization_alias="occurrenceCount")
    is_priority: bool = Field(default=False, serialization_alias="isPriority")
    booker_display_name: Optional[str] = Field(default=None, serialization_alias="bookerDisplayName")
    booker_email: Optional[str] = Field(default=None, serialization_alias="bookerEmail")
    is_booker: bool = Field(default=False, serialization_alias="isBooker")
    is_view_only: bool = Field(default=True, serialization_alias="isViewOnly")
    timeline: list[MemberBookingTimelineEvent] = Field(default_factory=list)
    actions: MemberBookingActions = Field(
        default_factory=lambda: MemberBookingActions(can_edit_title=False, can_cancel=False, can_view_payment_instructions=False, can_book_again=False)
    )
    occurrences: list[MemberBookingDetail] = Field(default_factory=list)


class MemberRecurringBookingConflict(BaseModel):
    """One unavailable occurrence in a Recurring Booking conflict preview."""

    occurrence_date: DateType = Field(..., serialization_alias="occurrenceDate")
    kind: str = Field(...)
    facility_ids: list[UUID] = Field(default_factory=list, serialization_alias="facilityIds")
    is_overridable: bool = Field(default=False, serialization_alias="isOverridable")
    ministry_id: Optional[UUID] = Field(default=None, serialization_alias="ministryId")
    ministry_steward_display_name: Optional[str] = Field(default=None, serialization_alias="ministryStewardDisplayName")
    ministry_steward_email: Optional[str] = Field(default=None, serialization_alias="ministryStewardEmail")


class MemberRecurringBookingPreview(BaseModel):
    """Recurring Booking conflict preview; does not persist a Series."""

    conflicts: list[MemberRecurringBookingConflict] = Field(default_factory=list)


class MemberRecurringBookingWindowStatus(BaseModel):
    """Whether Recurring Booking currently accepts new Series."""

    is_open: bool = Field(..., serialization_alias="isOpen")
    next_opening_date: Optional[DateType] = Field(default=None, serialization_alias="nextOpeningDate")
