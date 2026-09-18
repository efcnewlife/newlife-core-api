"""Participant authorization, lifecycle timeline, and Booker action eligibility."""

from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import PENDING_PAYMENT_HOLD_EXPIRED_REASON, BookingLifecycleEventKind, BookingStatus
from portal.domain.facility.participant_detail import booker_action_eligibility, build_booking_lifecycle_timeline, is_current_booking_participant


def test_booker_and_current_ministry_member_are_participants():
    booker_id = uuid4()
    member_id = uuid4()
    ministry_id = uuid4()
    assert is_current_booking_participant(viewer_id=booker_id, booker_id=booker_id, ministry_id=ministry_id, owned_ministry_ids=[]) is True
    assert is_current_booking_participant(viewer_id=member_id, booker_id=booker_id, ministry_id=ministry_id, owned_ministry_ids=[ministry_id]) is True


def test_former_member_and_unrelated_user_are_not_participants():
    booker_id = uuid4()
    ministry_id = uuid4()
    assert is_current_booking_participant(viewer_id=uuid4(), booker_id=booker_id, ministry_id=ministry_id, owned_ministry_ids=[]) is False
    assert is_current_booking_participant(viewer_id=uuid4(), booker_id=booker_id, ministry_id=None, owned_ministry_ids=[ministry_id]) is False


def test_timeline_includes_creation_cancellation_override_and_expiry_without_operator_or_replacement():
    created_at = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
    outcome_at = datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc)

    created = build_booking_lifecycle_timeline(status=BookingStatus.CONFIRMED.value, created_at=created_at, cancelled_at=None, cancel_reason=None)
    assert [(event.kind, event.occurred_at, event.reason) for event in created] == [(BookingLifecycleEventKind.CREATED.value, created_at, None)]

    cancelled = build_booking_lifecycle_timeline(
        status=BookingStatus.CANCELLED.value, created_at=created_at, cancelled_at=outcome_at, cancel_reason="Family conflict"
    )
    assert [(event.kind, event.occurred_at, event.reason) for event in cancelled] == [
        (BookingLifecycleEventKind.CREATED.value, created_at, None),
        (BookingLifecycleEventKind.CANCELLED.value, outcome_at, "Family conflict"),
    ]

    overridden = build_booking_lifecycle_timeline(
        status=BookingStatus.OVERRIDDEN.value, created_at=created_at, cancelled_at=outcome_at, cancel_reason="Replaced by choir ministry"
    )
    assert [(event.kind, event.occurred_at, event.reason) for event in overridden] == [
        (BookingLifecycleEventKind.CREATED.value, created_at, None),
        (BookingLifecycleEventKind.OVERRIDDEN.value, outcome_at, None),
    ]

    expired = build_booking_lifecycle_timeline(
        status=BookingStatus.CANCELLED.value, created_at=created_at, cancelled_at=outcome_at, cancel_reason=PENDING_PAYMENT_HOLD_EXPIRED_REASON
    )
    assert [(event.kind, event.occurred_at, event.reason) for event in expired] == [
        (BookingLifecycleEventKind.CREATED.value, created_at, None),
        (BookingLifecycleEventKind.PAYMENT_EXPIRED.value, outcome_at, PENDING_PAYMENT_HOLD_EXPIRED_REASON),
    ]


def test_booker_action_eligibility_covers_title_cancel_payment_and_future_override_rebook():
    tz = ZoneInfo("America/Toronto")
    now = datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc)
    future_start = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    past_start = datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc)
    hold_expires = datetime(2026, 9, 20, 16, 0, tzinfo=timezone.utc)

    booker_confirmed = booker_action_eligibility(
        is_booker=True, status=BookingStatus.CONFIRMED.value, start_at=future_start, payment_hold_expires_at=None, now=now, facility_tz=tz
    )
    assert booker_confirmed.can_edit_title is True
    assert booker_confirmed.can_cancel is True
    assert booker_confirmed.can_view_payment_instructions is False
    assert booker_confirmed.can_book_again is False
    assert booker_confirmed.book_again_date is None

    viewer = booker_action_eligibility(
        is_booker=False, status=BookingStatus.CONFIRMED.value, start_at=future_start, payment_hold_expires_at=None, now=now, facility_tz=tz
    )
    assert viewer.can_edit_title is False
    assert viewer.can_cancel is False
    assert viewer.can_view_payment_instructions is False
    assert viewer.can_book_again is False

    pending = booker_action_eligibility(
        is_booker=True, status=BookingStatus.PENDING_PAYMENT.value, start_at=future_start, payment_hold_expires_at=hold_expires, now=now, facility_tz=tz
    )
    assert pending.can_view_payment_instructions is True
    assert pending.can_cancel is True

    expired_hold = booker_action_eligibility(
        is_booker=True, status=BookingStatus.PENDING_PAYMENT.value, start_at=future_start, payment_hold_expires_at=now, now=now, facility_tz=tz
    )
    assert expired_hold.can_view_payment_instructions is False
    assert expired_hold.can_cancel is False

    future_override = booker_action_eligibility(
        is_booker=True, status=BookingStatus.OVERRIDDEN.value, start_at=future_start, payment_hold_expires_at=None, now=now, facility_tz=tz
    )
    assert future_override.can_book_again is True
    assert future_override.book_again_date == future_start.astimezone(tz).date()
    assert future_override.can_cancel is False

    past_override = booker_action_eligibility(
        is_booker=True, status=BookingStatus.OVERRIDDEN.value, start_at=past_start, payment_hold_expires_at=None, now=now, facility_tz=tz
    )
    assert past_override.can_book_again is False
    assert past_override.book_again_date is None

    series_override = booker_action_eligibility(
        is_booker=True, status=BookingStatus.OVERRIDDEN.value, start_at=future_start, payment_hold_expires_at=None, now=now, facility_tz=tz, series_level=True
    )
    assert series_override.can_book_again is False
    assert series_override.book_again_date is None
