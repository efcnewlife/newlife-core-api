"""Recurring Booking availability window helpers."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from portal.domain.facility.recurring import is_any_recurring_period_open, is_first_occurrence_in_availability_window, next_recurring_opening_date

TORONTO = ZoneInfo("America/Toronto")
FOUR_WEEKS = ("weeks", 4)


def test_september_is_outside_every_four_week_window():
    now_local = datetime(2026, 9, 17, 12, 0, tzinfo=TORONTO)
    amount = FOUR_WEEKS[1]
    unit = FOUR_WEEKS[0]
    assert is_any_recurring_period_open(now_local, amount, unit) is False
    assert is_first_occurrence_in_availability_window(now_local, date(2026, 8, 20), amount, unit) is False
    assert next_recurring_opening_date(now_local) == date(2026, 12, 1)


def test_early_december_opens_january_june_of_the_following_year():
    now_local = datetime(2025, 12, 8, 12, 0, tzinfo=TORONTO)
    amount = FOUR_WEEKS[1]
    unit = FOUR_WEEKS[0]
    assert is_any_recurring_period_open(now_local, amount, unit) is True
    assert is_first_occurrence_in_availability_window(now_local, date(2026, 1, 6), amount, unit) is True
    assert is_first_occurrence_in_availability_window(now_local, date(2026, 7, 7), amount, unit) is False
    assert next_recurring_opening_date(now_local) == date(2026, 6, 1)
