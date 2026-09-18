"""
Tests for the scheduled Mock Ministry inventory catalog.
"""

from datetime import date, time

from portal.application.cli.mock_ministry_inventory import (
    MOCK_MINISTRY_COUNT,
    build_mock_ministry_plans,
    ministry_display_name,
    ministry_purpose,
    secondary_steward_emails_for_index,
)
from portal.domain.facility.constants import DayOfWeek


def test_build_mock_ministry_plans_returns_ten_scheduled_labels():
    plans = build_mock_ministry_plans(year=2026)

    assert len(plans) == MOCK_MINISTRY_COUNT
    assert [plan.label for plan in plans] == [
        "Alpha",
        "Badminton",
        "Basketball",
        "Chinese School",
        "Pickleball",
        "Softball",
        "Stretching",
        "Supporting SOSO Ministry",
        "Choir",
        "Prayer",
    ]
    assert all(plan.purpose == ministry_purpose(plan.label) for plan in plans)


def test_build_mock_ministry_plans_uses_relative_seasonal_windows():
    plans = {plan.label: plan for plan in build_mock_ministry_plans(year=2027)}

    assert plans["Alpha"].schedule.effective_from == date(2027, 9, 1)
    assert plans["Alpha"].schedule.effective_to == date(2027, 9, 30)
    assert plans["Alpha"].schedule.days_of_week == ()
    assert plans["Chinese School"].schedule.effective_to == date(2028, 5, 31)
    assert plans["Badminton"].schedule.days_of_week == (DayOfWeek.SUNDAY,)
    assert plans["Badminton"].schedule.start_time == time(13, 30)
    assert plans["Badminton"].schedule.end_time == time(16, 30)


def test_ministry_display_name_carries_the_run_identity():
    assert ministry_display_name(label="Badminton", run_identity="dev-2026-09-17_1405") == "Mock Badminton (dev-2026-09-17_1405)"


def test_secondary_steward_emails_put_the_third_steward_on_the_first_half():
    stewards = ["steward.aaaa@test.local", "steward.bbbb@test.local", "steward.cccc@test.local"]

    first_half = secondary_steward_emails_for_index(0, stewards)
    second_half = secondary_steward_emails_for_index(5, stewards)

    assert first_half == ["steward.bbbb@test.local", "steward.cccc@test.local"]
    assert second_half == ["steward.bbbb@test.local"]
