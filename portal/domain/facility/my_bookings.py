"""My Bookings section classification for member browse."""

from datetime import datetime
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import BookingStatus, MyBookingsSection
from portal.domain.facility.recurring import is_pending_payment_hold_active

_ACTIVE_STATUSES = {BookingStatus.CONFIRMED.value, BookingStatus.PENDING_PAYMENT.value}


def classify_my_bookings_section(
    *, status: str, end_at: datetime, payment_hold_expires_at: datetime | None, now: datetime, facility_tz: ZoneInfo
) -> MyBookingsSection | None:
    """Return the My Bookings section for one Booking using facility-local end time."""
    if status == BookingStatus.OVERRIDDEN.value:
        return MyBookingsSection.OVERRIDDEN
    if status == BookingStatus.CANCELLED.value:
        return MyBookingsSection.CANCELLED_OR_EXPIRED
    if status == BookingStatus.PENDING_PAYMENT.value and not is_pending_payment_hold_active(payment_hold_expires_at, now):
        return MyBookingsSection.CANCELLED_OR_EXPIRED
    if status not in _ACTIVE_STATUSES:
        return None
    local_end = end_at.astimezone(facility_tz)
    local_now = now.astimezone(facility_tz)
    if local_end > local_now:
        return MyBookingsSection.UPCOMING
    return MyBookingsSection.PAST
