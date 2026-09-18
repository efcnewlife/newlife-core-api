"""
Recurring Booking Series date, window, and local-time helpers.
"""

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import BookingStatus, RecurringUsePeriod
from portal.domain.system.constants import RecurringAvailabilityUnit


def use_period_for_date(occurrence_date: date) -> RecurringUsePeriod:
    """Return the Recurring Booking period that contains the date."""
    if occurrence_date.month <= 6:
        return RecurringUsePeriod.JAN_JUN
    return RecurringUsePeriod.JUL_DEC


def opening_date_for_period(period: RecurringUsePeriod, period_year: int) -> date:
    """Facility-local opening date for a Recurring Booking period."""
    if period == RecurringUsePeriod.JAN_JUN:
        return date(period_year - 1, 12, 1)
    return date(period_year, 6, 1)


def add_availability_duration(start: date, amount: int, unit: str) -> date:
    """Add a days/weeks/calendar-months duration to an opening date."""
    if unit == RecurringAvailabilityUnit.DAYS.value:
        return start + timedelta(days=amount)
    if unit == RecurringAvailabilityUnit.WEEKS.value:
        return start + timedelta(weeks=amount)
    month_index = start.month - 1 + amount
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, monthrange(year, month)[1])
    return date(year, month, day)


def is_within_availability_window(now_local: datetime, opening: date, amount: int, unit: str) -> bool:
    """True when now is in [opening 00:00, opening + duration 00:00) local."""
    window_start = datetime.combine(opening, time.min, tzinfo=now_local.tzinfo)
    window_end = datetime.combine(add_availability_duration(opening, amount, unit), time.min, tzinfo=now_local.tzinfo)
    return window_start <= now_local < window_end


def is_first_occurrence_in_availability_window(now_local: datetime, first_occurrence_date: date, amount: int, unit: str) -> bool:
    """True when First occurrence's Recurring Booking period is currently accepting new Series."""
    period = use_period_for_date(first_occurrence_date)
    opening = opening_date_for_period(period, first_occurrence_date.year)
    return is_within_availability_window(now_local, opening, amount, unit)


def is_any_recurring_period_open(now_local: datetime, amount: int, unit: str) -> bool:
    """True when at least one Recurring Booking period is currently accepting new Series."""
    for year in range(now_local.year - 1, now_local.year + 3):
        for period in RecurringUsePeriod:
            opening = opening_date_for_period(period, year)
            if is_within_availability_window(now_local, opening, amount, unit):
                return True
    return False


def next_recurring_opening_date(now_local: datetime) -> date | None:
    """Next Recurring Booking opening date strictly after now, if any in the nearby years."""
    candidates: list[date] = []
    for year in range(now_local.year - 1, now_local.year + 3):
        for period in RecurringUsePeriod:
            opening = opening_date_for_period(period, year)
            opening_at = datetime.combine(opening, time.min, tzinfo=now_local.tzinfo)
            if opening_at > now_local:
                candidates.append(opening)
    if not candidates:
        return None
    return min(candidates)


def weekly_occurrence_dates(first_occurrence_date: date, last_occurrence_date: date) -> list[date]:
    """Materialize weekly dates from first through last inclusive."""
    dates: list[date] = []
    current = first_occurrence_date
    while current <= last_occurrence_date:
        dates.append(current)
        current += timedelta(days=7)
    return dates


def sunday_week_start(occurrence_date: date) -> date:
    """Facility-local Sunday that starts the Sunday-Saturday quota week."""
    return occurrence_date - timedelta(days=(occurrence_date.weekday() + 1) % 7)


def localize_wall_time(occurrence_date: date, local_time: time, tz: ZoneInfo) -> datetime:
    """
    Interpret a local wall-clock time in the facility timezone.

    Ambiguous DST times use the earlier offset (fold=0). Nonexistent times raise ValueError.
    """
    naive = datetime.combine(occurrence_date, local_time)
    earlier = naive.replace(tzinfo=tz, fold=0)
    roundtrip = earlier.astimezone(timezone.utc).astimezone(tz)
    if roundtrip.replace(tzinfo=None) != naive:
        raise ValueError("nonexistent local time")
    return earlier


def is_church_email(email: str | None, domain: str) -> bool:
    """True when the email uses the church domain."""
    if not email or "@" not in email:
        return False
    return email.rsplit("@", 1)[-1].lower() == domain.lower()


def is_test_booker_allowlisted(email: str | None, email_addresses: list[str], email_suffixes: list[str]) -> bool:
    """True when email exactly matches an allowlisted address or a complete domain suffix.

    Callers must pass already-normalized (trimmed, lowercased) allowlist entries;
    the candidate email is normalized here.
    """
    if not email:
        return False
    candidate = email.strip().lower()
    if candidate in email_addresses:
        return True
    return any(candidate.endswith(suffix) for suffix in email_suffixes)


def is_pending_payment_hold_active(payment_hold_expires_at: datetime | None, now: datetime) -> bool:
    """True when a Pending-payment hold still reserves occupancy at query time."""
    if payment_hold_expires_at is None:
        return True
    return payment_hold_expires_at > now


def is_logically_occupying(*, booking_status: str, payment_hold_expires_at: datetime | None, now: datetime) -> bool:
    """True when a Booking still occupies a room, including an unexpired Pending-payment hold."""
    if booking_status == BookingStatus.CONFIRMED.value:
        return True
    if booking_status != BookingStatus.PENDING_PAYMENT.value:
        return False
    return is_pending_payment_hold_active(payment_hold_expires_at, now)
