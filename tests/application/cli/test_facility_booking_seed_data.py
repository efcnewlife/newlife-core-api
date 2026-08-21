"""
Tests for demo facility booking seed plans and personal Booker accounts.
"""

from datetime import date

from portal.cli.datas.facility_booking_seed_data import (
    BOOKING_SEED_REMARK_PREFIX,
    DEMO_PERSONAL_BOOKER_EMAILS,
    DEMO_PRIMARY_USER_EMAIL,
    DEMO_SECONDARY_2_USER_EMAIL,
    DEMO_SECONDARY_USER_EMAIL,
    build_demo_booking_plans,
    demo_personal_booker_seed_rows,
)
from portal.cli.datas.ministry_seed_data import SEED_NAME_PREFIX as MINISTRY_SEED_PREFIX


def test_five_personal_booker_accounts():
    assert len(demo_personal_booker_seed_rows) == 5
    assert [row["email"] for row in demo_personal_booker_seed_rows] == list(DEMO_PERSONAL_BOOKER_EMAILS)
    for row in demo_personal_booker_seed_rows:
        assert row["email"].startswith("seed.booker.")
        assert row["first_name"]
        assert row["last_name"]


def test_booking_plans_cover_bookers_multi_room_and_ministry_split():
    today = date(2026, 8, 21)
    plans = build_demo_booking_plans(today=today)

    assert 8 <= len(plans) <= 12
    assert all(plan["remark"].startswith(BOOKING_SEED_REMARK_PREFIX) for plan in plans)

    personal_plans = [plan for plan in plans if plan["ministry_english_name"] is None]
    ministry_plans = [plan for plan in plans if plan["ministry_english_name"] is not None]
    assert len(personal_plans) >= 5
    assert len(ministry_plans) >= 3

    personal_bookers = {plan["booker_email"] for plan in personal_plans}
    assert personal_bookers == set(DEMO_PERSONAL_BOOKER_EMAILS)

    ministry_bookers = {plan["booker_email"] for plan in ministry_plans}
    assert DEMO_PRIMARY_USER_EMAIL in ministry_bookers
    assert DEMO_SECONDARY_USER_EMAIL in ministry_bookers
    assert DEMO_SECONDARY_2_USER_EMAIL in ministry_bookers

    multi_room = [plan for plan in plans if len(plan["room_codes"]) >= 2]
    assert multi_room, "expected at least one multi-room booking"

    for plan in plans:
        assert plan["end_hour"] > plan["start_hour"]
        assert isinstance(plan["day_offset"], int)
        assert plan["room_codes"]
        if plan["ministry_english_name"] is not None:
            assert not plan["ministry_english_name"].startswith(MINISTRY_SEED_PREFIX)


def test_booking_plans_skip_campus_wide_blackout_day():
    from datetime import timedelta

    from portal.cli.datas.facility_slot_seed_data import CAMPUS_HOLIDAY_DEMO_DATE

    today = CAMPUS_HOLIDAY_DEMO_DATE - timedelta(days=1)
    plans = build_demo_booking_plans(today=today)
    for plan in plans:
        local_day = today + timedelta(days=plan["day_offset"])
        assert local_day != CAMPUS_HOLIDAY_DEMO_DATE
