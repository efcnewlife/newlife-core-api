"""
Tests for the demo ministry seed rows and seed prerequisite checks.
"""

from datetime import date, time

import pytest

from portal.application.cli.ministry_seed_service import assert_seed_prerequisites
from portal.cli.datas.ministry_seed_data import (
    DEMO_PRIMARY_USER_EMAIL,
    DEMO_SECONDARY_2_USER_EMAIL,
    DEMO_SECONDARY_USER_EMAIL,
    SEED_LOCALE_CODES,
    SEED_NAME_PREFIX,
    demo_ministry_user_seed_rows,
    ministry_seed_rows,
    secondary_steward_emails_for_ministry_index,
)
from portal.domain.facility.constants import DayOfWeek
from portal.domain.org.catalog_codes import (
    MINISTRY_TYPE_INTERNAL,
    MINISTRY_TYPE_OUTREACH,
    MINISTRY_TYPE_WORSHIP,
    TARGET_AUDIENCE_ADULTS,
    TARGET_AUDIENCE_ALL_AGES,
    TARGET_AUDIENCE_CHILDREN,
    TARGET_AUDIENCE_FAMILY,
    TARGET_AUDIENCE_YOUTHS,
)


def _row_by_english_name(name: str) -> dict:
    """Look up a seed row by its unprefixed English name."""
    full_name = f"{SEED_NAME_PREFIX}{name}"
    for row in ministry_seed_rows:
        if row["translations"]["en"]["name"] == full_name:
            return row
    raise AssertionError(f"seed row {name!r} not found")


def test_seed_defines_ten_ministries():
    assert len(ministry_seed_rows) == 10


def test_every_locale_name_starts_with_seed_prefix():
    for row in ministry_seed_rows:
        for locale_code in SEED_LOCALE_CODES:
            name = row["translations"][locale_code]["name"]
            assert name.startswith(SEED_NAME_PREFIX), f"{locale_code} name {name!r} missing prefix"


def test_every_ministry_has_all_three_locales():
    for row in ministry_seed_rows:
        assert set(row["translations"]) == set(SEED_LOCALE_CODES)


def test_english_names_match_the_frozen_program_table():
    english_names = [row["translations"]["en"]["name"] for row in ministry_seed_rows]
    assert english_names == [
        f"{SEED_NAME_PREFIX}{name}"
        for name in [
            "Alpha 2026",
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
    ]


@pytest.mark.parametrize(
    "locale_code,expected",
    [
        ("zh-TW", ["啟發 2026", "羽毛球", "籃球", "中文學校", "皮克球", "壘球", "拉筋班", "支援 SOSO 事工", "詩班", "禱告"]),
        ("zh-CN", ["启发 2026", "羽毛球", "篮球", "中文学校", "皮克球", "垒球", "拉筋班", "支援 SOSO 事工", "诗班", "祷告"]),
    ],
)
def test_localized_names_match_the_frozen_program_table(locale_code: str, expected: list[str]):
    names = [row["translations"][locale_code]["name"] for row in ministry_seed_rows]
    assert names == [f"{SEED_NAME_PREFIX}{name}" for name in expected]


def test_only_alpha_and_badminton_have_priority_booking():
    flags = [row["has_priority_booking"] for row in ministry_seed_rows]
    assert flags == [True, True, False, False, False, False, False, False, False, False]


def test_alpha_is_an_annual_ministry_with_september_window_and_tba_times():
    row = _row_by_english_name("Alpha 2026")

    assert "2026" in row["translations"]["en"]["name"]
    assert "2026" in row["translations"]["zh-TW"]["name"]
    assert "2026" in row["translations"]["zh-CN"]["name"]

    assert len(row["schedules"]) == 1
    schedule = row["schedules"][0]
    assert schedule["start_time"] is None
    assert schedule["end_time"] is None
    assert schedule["effective_from"] == date(2026, 9, 1)
    assert schedule["effective_to"] == date(2026, 9, 30)
    assert row["ministry_type_code"] == MINISTRY_TYPE_OUTREACH
    assert row["target_audience_codes"] == [TARGET_AUDIENCE_ADULTS]


def test_choir_is_a_worship_ministry_on_sunday_morning():
    row = _row_by_english_name("Choir")

    assert row["ministry_type_code"] == MINISTRY_TYPE_WORSHIP
    assert row["target_audience_codes"] == [TARGET_AUDIENCE_ALL_AGES]
    assert row["schedules"] == [
        {"days_of_week": [DayOfWeek.SUNDAY], "start_time": time(9, 0), "end_time": time(10, 30), "effective_from": None, "effective_to": None}
    ]


def test_prayer_is_a_wednesday_evening_ministry():
    row = _row_by_english_name("Prayer")

    assert row["ministry_type_code"] == MINISTRY_TYPE_INTERNAL
    assert row["target_audience_codes"] == [TARGET_AUDIENCE_ADULTS]
    assert row["schedules"] == [
        {"days_of_week": [DayOfWeek.WEDNESDAY], "start_time": time(19, 30), "end_time": time(21, 0), "effective_from": None, "effective_to": None}
    ]


def test_basketball_targets_children_and_youths_on_saturday_afternoon():
    row = _row_by_english_name("Basketball")

    assert row["target_audience_codes"] == [TARGET_AUDIENCE_CHILDREN, TARGET_AUDIENCE_YOUTHS]
    assert row["schedules"][0]["days_of_week"] == [DayOfWeek.SATURDAY]
    assert row["schedules"][0]["start_time"] == time(14, 0)
    assert row["schedules"][0]["end_time"] == time(18, 0)


def test_pickleball_runs_three_weekdays():
    row = _row_by_english_name("Pickleball")

    assert row["schedules"][0]["days_of_week"] == [DayOfWeek.TUESDAY, DayOfWeek.THURSDAY, DayOfWeek.SATURDAY]
    assert row["schedules"][0]["start_time"] == time(9, 30)
    assert row["schedules"][0]["end_time"] == time(12, 0)


def test_softball_uses_a_summer_only_seasonal_schedule():
    row = _row_by_english_name("Softball")

    assert row["target_audience_codes"] == [TARGET_AUDIENCE_ALL_AGES]
    schedule = row["schedules"][0]
    assert schedule["days_of_week"] == [DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]
    assert schedule["start_time"] == time(15, 0)
    assert schedule["end_time"] == time(18, 0)
    assert schedule["effective_from"] == date(2026, 6, 1)
    assert schedule["effective_to"] == date(2026, 8, 31)


@pytest.mark.parametrize("english_name", ["Chinese School", "Stretching"])
def test_summer_except_programs_use_a_school_year_seasonal_schedule(english_name: str):
    row = _row_by_english_name(english_name)

    schedule = row["schedules"][0]
    assert schedule["effective_from"] == date(2026, 9, 1)
    assert schedule["effective_to"] == date(2027, 5, 31)


def test_chinese_school_keeps_the_adult_conversation_caveat_in_every_locale():
    row = _row_by_english_name("Chinese School")

    assert row["target_audience_codes"] == [TARGET_AUDIENCE_CHILDREN, TARGET_AUDIENCE_ADULTS]
    for locale_code in SEED_LOCALE_CODES:
        assert row["translations"][locale_code]["schedule_note"]


def test_soso_keeps_a_monday_window_plus_a_special_occasion_note():
    row = _row_by_english_name("Supporting SOSO Ministry")

    assert row["ministry_type_code"] == MINISTRY_TYPE_OUTREACH
    assert row["target_audience_codes"] == [TARGET_AUDIENCE_ADULTS, TARGET_AUDIENCE_FAMILY]
    schedule = row["schedules"][0]
    assert schedule["days_of_week"] == [DayOfWeek.MONDAY]
    assert schedule["start_time"] == time(10, 0)
    assert schedule["end_time"] == time(15, 0)
    for locale_code in SEED_LOCALE_CODES:
        assert row["translations"][locale_code]["schedule_note"]


def test_badminton_runs_sunday_afternoon():
    row = _row_by_english_name("Badminton")

    assert row["schedules"][0]["days_of_week"] == [DayOfWeek.SUNDAY]
    assert row["schedules"][0]["start_time"] == time(13, 30)
    assert row["schedules"][0]["end_time"] == time(16, 30)


def test_all_ages_is_never_combined_with_another_audience():
    for row in ministry_seed_rows:
        codes = row["target_audience_codes"]
        if TARGET_AUDIENCE_ALL_AGES in codes:
            assert codes == [TARGET_AUDIENCE_ALL_AGES]


def test_every_schedule_has_a_weekday_or_an_effective_window():
    for row in ministry_seed_rows:
        assert row["schedules"], row["translations"]["en"]["name"]
        for schedule in row["schedules"]:
            assert schedule["days_of_week"] or schedule["effective_from"]
            assert (schedule["start_time"] is None) == (schedule["end_time"] is None)
            if schedule["start_time"] and schedule["end_time"]:
                assert schedule["start_time"] < schedule["end_time"]


def test_demo_steward_users_are_one_primary_and_two_secondaries():
    assert [row["email"] for row in demo_ministry_user_seed_rows] == [DEMO_PRIMARY_USER_EMAIL, DEMO_SECONDARY_USER_EMAIL, DEMO_SECONDARY_2_USER_EMAIL]
    assert DEMO_PRIMARY_USER_EMAIL == "seed.ministry.primary@local.test"
    assert DEMO_SECONDARY_USER_EMAIL == "seed.ministry.secondary@local.test"
    assert DEMO_SECONDARY_2_USER_EMAIL == "seed.ministry.secondary2@local.test"
    for row in demo_ministry_user_seed_rows:
        assert row["first_name"]
        assert row["last_name"]


def test_first_half_ministries_get_two_secondaries_second_half_get_one():
    total = len(ministry_seed_rows)
    midpoint = total // 2
    for index in range(total):
        emails = secondary_steward_emails_for_ministry_index(index, total=total)
        if index < midpoint:
            assert emails == [DEMO_SECONDARY_USER_EMAIL, DEMO_SECONDARY_2_USER_EMAIL]
        else:
            assert emails == [DEMO_SECONDARY_USER_EMAIL]


def _prerequisites(**overrides):
    kwargs = dict(
        locale_codes=set(SEED_LOCALE_CODES),
        ministry_type_codes={MINISTRY_TYPE_OUTREACH, MINISTRY_TYPE_INTERNAL, MINISTRY_TYPE_WORSHIP},
        target_audience_codes={TARGET_AUDIENCE_CHILDREN, TARGET_AUDIENCE_YOUTHS, TARGET_AUDIENCE_ADULTS, TARGET_AUDIENCE_FAMILY, TARGET_AUDIENCE_ALL_AGES},
        owning_position_count=3,
    )
    kwargs.update(overrides)
    return kwargs


def test_prerequisites_pass_when_every_catalog_is_seeded():
    assert_seed_prerequisites(ministry_seed_rows, **_prerequisites())


def test_missing_locale_names_the_locale_seed():
    with pytest.raises(ValueError, match="init-locales"):
        assert_seed_prerequisites(ministry_seed_rows, **_prerequisites(locale_codes={"en"}))


def test_missing_ministry_type_names_the_ministry_type_seed():
    with pytest.raises(ValueError, match="seed-ministry-types"):
        assert_seed_prerequisites(ministry_seed_rows, **_prerequisites(ministry_type_codes={MINISTRY_TYPE_INTERNAL}))


def test_missing_target_audience_names_the_target_audience_seed():
    with pytest.raises(ValueError, match="seed-target-audiences"):
        assert_seed_prerequisites(ministry_seed_rows, **_prerequisites(target_audience_codes={TARGET_AUDIENCE_ADULTS}))


def test_missing_owning_position_names_the_position_seed():
    with pytest.raises(ValueError, match="seed-positions"):
        assert_seed_prerequisites(ministry_seed_rows, **_prerequisites(owning_position_count=0))
