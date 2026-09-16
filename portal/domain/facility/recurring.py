"""
Recurring Booking Series date, window, and local-time helpers.
"""

from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import RecurringUsePeriod
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
