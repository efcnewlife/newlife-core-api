"""
Tests for demo facility slot template and blackout seed rows.
"""

from datetime import time

from portal.cli.datas.facility_rental_seed_data import facility_room_seed_rows
from portal.cli.datas.facility_slot_seed_data import (
    SEED_NAME_PREFIX,
    SUNDAY_MORNING_BLACKOUT_ROOM_CODES,
    build_slot_template_rows_for_room_codes,
    facility_blackout_seed_rows,
)
from portal.domain.facility.constants import DayOfWeek, RoomBlackoutKind
from portal.domain.facility.days_of_week_mask import days_to_mask, mask_to_days


def test_slot_templates_cover_every_catalog_room_all_week_0800_to_2200():
    room_codes = [row["code"] for row in facility_room_seed_rows]
    slots = build_slot_template_rows_for_room_codes(room_codes)

    assert len(slots) == len(room_codes)
    assert {row["room_code"] for row in slots} == set(room_codes)
    for row in slots:
        assert row["name"].startswith(SEED_NAME_PREFIX)
        assert mask_to_days(row["days_of_week_mask"]) == list(range(DayOfWeek.MONDAY, DayOfWeek.SUNDAY + 1))
        assert row["start_time"] == time(8, 0)
        assert row["end_time"] == time(22, 0)
        assert row["slot_duration_minutes"] == 60
        assert row["is_active"] is True


def test_blackouts_keep_legacy_demos_and_add_sunday_morning_on_three_rooms():
    names = [row["name"] for row in facility_blackout_seed_rows]
    assert all(name.startswith(SEED_NAME_PREFIX) for name in names)

    sunday_rows = [row for row in facility_blackout_seed_rows if "Sunday morning" in row["name"]]
    assert {row["room_code"] for row in sunday_rows} == set(SUNDAY_MORNING_BLACKOUT_ROOM_CODES)
    assert SUNDAY_MORNING_BLACKOUT_ROOM_CODES == ("sanctuary-hall", "gym", "lobby")
    for row in sunday_rows:
        assert row["kind"] == RoomBlackoutKind.RECURRING.value
        assert row["days_of_week_mask"] == days_to_mask([DayOfWeek.SUNDAY])
        assert row["start_time"] == time(8, 0)
        assert row["end_time"] == time(13, 0)

    legacy_names = {f"{SEED_NAME_PREFIX}Campus holiday demo", f"{SEED_NAME_PREFIX}Wednesday afternoon closed", f"{SEED_NAME_PREFIX}Maintenance demo"}
    assert legacy_names.issubset(set(names))
    assert len(facility_blackout_seed_rows) == 6
