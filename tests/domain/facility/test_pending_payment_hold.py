"""
Query-time Pending-payment hold occupancy.
"""

from datetime import datetime, timedelta, timezone

from portal.domain.facility.constants import BookingStatus
from portal.domain.facility.recurring import is_logically_occupying, is_pending_payment_hold_active

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def test_unexpired_hold_is_active():
    assert is_pending_payment_hold_active(NOW + timedelta(hours=1), NOW) is True


def test_elapsed_hold_is_not_active():
    assert is_pending_payment_hold_active(NOW - timedelta(seconds=1), NOW) is False


def test_missing_hold_deadline_stays_active():
    assert is_pending_payment_hold_active(None, NOW) is True


def test_confirmed_booking_occupies_after_hold_elapsed():
    assert is_logically_occupying(booking_status=BookingStatus.CONFIRMED.value, payment_hold_expires_at=NOW - timedelta(hours=1), now=NOW) is True


def test_pending_payment_occupies_only_while_hold_is_active():
    assert is_logically_occupying(booking_status=BookingStatus.PENDING_PAYMENT.value, payment_hold_expires_at=NOW + timedelta(hours=1), now=NOW) is True
    assert is_logically_occupying(booking_status=BookingStatus.PENDING_PAYMENT.value, payment_hold_expires_at=NOW, now=NOW) is False


def test_cancelled_booking_does_not_occupy():
    assert is_logically_occupying(booking_status=BookingStatus.CANCELLED.value, payment_hold_expires_at=NOW + timedelta(hours=1), now=NOW) is False
