"""Participant Booking detail authorization, timeline, and Booker action eligibility."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import PENDING_PAYMENT_HOLD_EXPIRED_REASON, BookingLifecycleEventKind, BookingStatus
from portal.domain.facility.recurring import as_utc, is_pending_payment_hold_active

_LIVE_STATUSES = {BookingStatus.CONFIRMED.value, BookingStatus.PENDING_PAYMENT.value}


@dataclass(frozen=True)
class BookingLifecycleEvent:
    """One member-visible lifecycle timeline entry."""

    kind: str
    occurred_at: datetime
    reason: Optional[str] = None


@dataclass(frozen=True)
class BookerActionEligibility:
    """Booker-only self-service flags for one Booking or Series."""

    can_edit_title: bool
    can_cancel: bool
    can_view_payment_instructions: bool
    can_book_again: bool
    book_again_date: Optional[date] = None


_NO_ACTIONS = BookerActionEligibility(can_edit_title=False, can_cancel=False, can_view_payment_instructions=False, can_book_again=False, book_again_date=None)


def is_current_booking_participant(*, viewer_id: UUID, booker_id: UUID, ministry_id: Optional[UUID], owned_ministry_ids: list[UUID]) -> bool:
    """True when the viewer is the Booker or a current member of the Booking's Active Ministry."""
    if viewer_id == booker_id:
        return True
    if ministry_id is not None and ministry_id in owned_ministry_ids:
        return True
    return False


def build_booking_lifecycle_timeline(
    *, status: str, created_at: Optional[datetime], cancelled_at: Optional[datetime], cancel_reason: Optional[str]
) -> list[BookingLifecycleEvent]:
    """Build creation and outcome events without Operator or replacement activity."""
    events: list[BookingLifecycleEvent] = []
    if created_at is not None:
        events.append(BookingLifecycleEvent(kind=BookingLifecycleEventKind.CREATED.value, occurred_at=created_at))
    if cancelled_at is None:
        return events
    if status == BookingStatus.OVERRIDDEN.value:
        events.append(BookingLifecycleEvent(kind=BookingLifecycleEventKind.OVERRIDDEN.value, occurred_at=cancelled_at))
        return events
    if status != BookingStatus.CANCELLED.value:
        return events
    if cancel_reason == PENDING_PAYMENT_HOLD_EXPIRED_REASON:
        events.append(
            BookingLifecycleEvent(kind=BookingLifecycleEventKind.PAYMENT_EXPIRED.value, occurred_at=cancelled_at, reason=PENDING_PAYMENT_HOLD_EXPIRED_REASON)
        )
        return events
    events.append(BookingLifecycleEvent(kind=BookingLifecycleEventKind.CANCELLED.value, occurred_at=cancelled_at, reason=cancel_reason))
    return events


def booker_action_eligibility(
    *,
    is_booker: bool,
    status: str,
    start_at: datetime,
    payment_hold_expires_at: Optional[datetime],
    now: datetime,
    facility_tz: ZoneInfo,
    series_level: bool = False,
) -> BookerActionEligibility:
    """Compute Booker-only title, cancel, payment-instruction, and Book again eligibility."""
    if not is_booker:
        return _NO_ACTIONS
    hold_active = is_pending_payment_hold_active(payment_hold_expires_at, now)
    pending_expired = status == BookingStatus.PENDING_PAYMENT.value and not hold_active
    local_start = as_utc(start_at).astimezone(facility_tz)
    local_now = as_utc(now).astimezone(facility_tz)
    is_future = local_start > local_now
    can_cancel = (not pending_expired) and status in _LIVE_STATUSES and is_future
    can_view_payment_instructions = status == BookingStatus.PENDING_PAYMENT.value and hold_active
    can_book_again = (not series_level) and status == BookingStatus.OVERRIDDEN.value and is_future
    return BookerActionEligibility(
        can_edit_title=True,
        can_cancel=can_cancel,
        can_view_payment_instructions=can_view_payment_instructions,
        can_book_again=can_book_again,
        book_again_date=local_start.date() if can_book_again else None,
    )
