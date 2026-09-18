"""Assemble participant-authorized Booking detail from a Booking row."""

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.results import (
    BookingDetailResult,
    ParticipantActionEligibilityResult,
    ParticipantBookingDetailResult,
    ParticipantRoomLineResult,
    ParticipantSeriesDetailResult,
    ParticipantTimelineEventResult,
    RecurringBookingSeriesResult,
)
from portal.domain.facility.constants import ROOM_GALLERY_MAX_FILES
from portal.domain.facility.participant_detail import booker_action_eligibility, build_booking_lifecycle_timeline


def assemble_participant_booking_detail(
    row: BookingDetailResult, *, viewer_id: UUID, now: datetime, facility_tz: ZoneInfo, photo_urls_by_room: dict[UUID, list[str]], series_level: bool = False
) -> ParticipantBookingDetailResult:
    """Project a Booking row into the member-visible detail contract."""
    is_booker = row.user_id == viewer_id
    eligibility = booker_action_eligibility(
        is_booker=is_booker,
        status=row.status,
        start_at=row.start_at,
        payment_hold_expires_at=row.payment_hold_expires_at,
        now=now,
        facility_tz=facility_tz,
        series_level=series_level,
    )
    timeline = [
        ParticipantTimelineEventResult(kind=event.kind, occurred_at=event.occurred_at, reason=event.reason)
        for event in build_booking_lifecycle_timeline(
            status=row.status, created_at=row.created_at, cancelled_at=row.cancelled_at, cancel_reason=row.cancel_reason
        )
    ]
    rooms = [
        ParticipantRoomLineResult(
            id=line.id,
            facility_id=line.facility_id,
            facility_name=line.facility_name,
            sequence=line.sequence,
            start_at=line.start_at,
            end_at=line.end_at,
            billed_hours=line.billed_hours,
            rental_rate_name=line.rental_rate_name,
            billing_unit=line.billing_unit,
            unit_amount=line.unit_amount,
            currency=line.currency,
            line_subtotal=line.line_subtotal,
            photo_urls=photo_urls_by_room.get(line.facility_id, [])[:ROOM_GALLERY_MAX_FILES],
        )
        for line in row.rooms
    ]
    return ParticipantBookingDetailResult(
        id=row.id,
        title=row.title,
        status=row.status,
        booking_type=row.booking_type,
        series_id=row.series_id,
        start_at=row.start_at,
        end_at=row.end_at,
        ministry_id=row.ministry_id,
        ministry_name=row.ministry_name,
        remark=row.remark,
        booker_display_name=row.user_display_name,
        booker_email=row.user_email,
        subtotal_amount=row.subtotal_amount,
        discount_percent=row.discount_percent,
        discount_amount=row.discount_amount,
        surcharge_amount=row.surcharge_amount,
        quoted_amount=row.quoted_amount,
        currency=row.currency,
        payment_hold_expires_at=row.payment_hold_expires_at if eligibility.can_view_payment_instructions else None,
        is_booker=is_booker,
        is_view_only=not is_booker,
        rooms=rooms,
        timeline=timeline,
        actions=ParticipantActionEligibilityResult(
            can_edit_title=eligibility.can_edit_title,
            can_cancel=eligibility.can_cancel,
            can_view_payment_instructions=eligibility.can_view_payment_instructions,
            can_book_again=eligibility.can_book_again,
            book_again_date=eligibility.book_again_date,
        ),
    )


def assemble_participant_series_detail(
    series: RecurringBookingSeriesResult, occurrences: list[ParticipantBookingDetailResult], *, viewer_id: UUID, now: datetime, facility_tz: ZoneInfo
) -> ParticipantSeriesDetailResult:
    """Project a Recurring Booking Series and its Occurrences into member detail."""
    is_booker = series.user_id == viewer_id
    start_at = occurrences[0].start_at if occurrences else datetime.combine(series.first_occurrence_date, series.local_start_time).replace(tzinfo=facility_tz)
    eligibility = booker_action_eligibility(
        is_booker=is_booker,
        status=series.status,
        start_at=start_at,
        payment_hold_expires_at=series.payment_hold_expires_at,
        now=now,
        facility_tz=facility_tz,
        series_level=True,
    )
    can_cancel = is_booker and any(item.actions.can_cancel for item in occurrences)
    timeline = [
        ParticipantTimelineEventResult(kind=event.kind, occurred_at=event.occurred_at, reason=event.reason)
        for event in build_booking_lifecycle_timeline(status=series.status, created_at=series.created_at, cancelled_at=None, cancel_reason=None)
    ]
    return ParticipantSeriesDetailResult(
        id=series.id,
        title=series.title,
        status=series.status,
        ministry_id=series.ministry_id,
        ministry_name=series.ministry_name,
        remark=series.remark,
        first_occurrence_date=series.first_occurrence_date,
        last_occurrence_date=series.last_occurrence_date,
        local_start_time=series.local_start_time,
        local_end_time=series.local_end_time,
        payment_hold_expires_at=series.payment_hold_expires_at if eligibility.can_view_payment_instructions else None,
        quoted_amount=series.quoted_amount,
        currency=series.currency,
        occurrence_count=len(occurrences),
        booker_display_name=series.user_display_name or (occurrences[0].booker_display_name if occurrences else None),
        booker_email=series.user_email or (occurrences[0].booker_email if occurrences else None),
        is_booker=is_booker,
        is_view_only=not is_booker,
        timeline=timeline,
        actions=ParticipantActionEligibilityResult(
            can_edit_title=eligibility.can_edit_title,
            can_cancel=can_cancel,
            can_view_payment_instructions=eligibility.can_view_payment_instructions,
            can_book_again=False,
            book_again_date=None,
        ),
        occurrences=occurrences,
    )
