"""
Demo facility booking seed plans and personal Booker accounts.

Booking remarks use the ``seed:`` prefix so re-seed can replace only demo rows.
Wall-clock hours are local (America/Toronto); the seed service converts to UTC.
"""

from datetime import date, timedelta
from typing import Any, Optional

from portal.cli.datas.facility_slot_seed_data import CAMPUS_HOLIDAY_DEMO_DATE, SANCTUARY_MAINTENANCE_DEMO_DATE
from portal.cli.datas.ministry_seed_data import DEMO_PRIMARY_USER_EMAIL, DEMO_SECONDARY_2_USER_EMAIL, DEMO_SECONDARY_USER_EMAIL

BOOKING_SEED_REMARK_PREFIX = "seed:"

DEMO_PERSONAL_BOOKER_EMAILS = (
    "seed.booker.1@local.test",
    "seed.booker.2@local.test",
    "seed.booker.3@local.test",
    "seed.booker.4@local.test",
    "seed.booker.5@local.test",
)

demo_personal_booker_seed_rows: list[dict[str, Any]] = [
    {"email": email, "first_name": "Seed", "last_name": f"Booker{index}"} for index, email in enumerate(DEMO_PERSONAL_BOOKER_EMAILS, start=1)
]

# Campus-wide one-off Blackout dates (avoid for all rooms).
_CAMPUS_WIDE_BLACKOUT_DATES = frozenset({CAMPUS_HOLIDAY_DEMO_DATE})
# Room-specific one-off; only skip when the plan books that room.
_SANCTUARY_BLACKOUT_DATES = frozenset({SANCTUARY_MAINTENANCE_DEMO_DATE})


def _plan(
    *,
    remark_suffix: str,
    booker_email: str,
    room_codes: list[str],
    day_offset: int,
    start_hour: int,
    end_hour: int,
    ministry_english_name: Optional[str] = None,
) -> dict[str, Any]:
    return {
        "remark": f"{BOOKING_SEED_REMARK_PREFIX}{remark_suffix}",
        "booker_email": booker_email,
        "room_codes": list(room_codes),
        "day_offset": day_offset,
        "start_hour": start_hour,
        "end_hour": end_hour,
        "ministry_english_name": ministry_english_name,
    }


def _shift_offset_off_blackouts(*, today: date, preferred_offset: int, room_codes: list[str]) -> int:
    """Bump day_offset forward until the local calendar day avoids known one-off Blackouts."""
    offset = preferred_offset
    for _ in range(21):
        local_day = today + timedelta(days=offset)
        if local_day in _CAMPUS_WIDE_BLACKOUT_DATES:
            offset += 1
            continue
        if "sanctuary-hall" in room_codes and local_day in _SANCTUARY_BLACKOUT_DATES:
            offset += 1
            continue
        return offset
    raise ValueError(f"Could not place booking off Blackout dates from {today} offset {preferred_offset}")


def build_demo_booking_plans(*, today: date) -> list[dict[str, Any]]:
    """
    Build 8-12 near-term demo Booking plans relative to ``today``.

    Avoids Sunday 08:00-13:00 on sanctuary/gym/lobby and gym Wednesday 14:00-16:00
    by using weekday afternoons / evenings on those rooms. Shifts day offsets away
    from fixed one-off Blackout demo dates.
    """
    drafts: list[dict[str, Any]] = [
        {
            "remark_suffix": "personal-1 classroom-105",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[0],
            "room_codes": ["classroom-105"],
            "preferred_offset": 1,
            "start_hour": 10,
            "end_hour": 11,
        },
        {
            "remark_suffix": "personal-2 classroom-106",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[1],
            "room_codes": ["classroom-106"],
            "preferred_offset": 1,
            "start_hour": 11,
            "end_hour": 12,
        },
        {
            "remark_suffix": "personal-3 lounge",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[2],
            "room_codes": ["lounge"],
            "preferred_offset": 2,
            "start_hour": 14,
            "end_hour": 15,
        },
        {
            "remark_suffix": "personal-4 meeting-room",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[3],
            "room_codes": ["meeting-room"],
            "preferred_offset": 2,
            "start_hour": 15,
            "end_hour": 16,
        },
        {
            "remark_suffix": "personal-5 nursery",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[4],
            "room_codes": ["nursery"],
            "preferred_offset": 3,
            "start_hour": 10,
            "end_hour": 11,
        },
        {
            "remark_suffix": "ministry-primary gym evening",
            "booker_email": DEMO_PRIMARY_USER_EMAIL,
            "room_codes": ["gym"],
            "preferred_offset": 1,
            "start_hour": 18,
            "end_hour": 19,
            "ministry_english_name": "Badminton",
        },
        {
            "remark_suffix": "ministry-secondary classroom-125",
            "booker_email": DEMO_SECONDARY_USER_EMAIL,
            "room_codes": ["classroom-125"],
            "preferred_offset": 4,
            "start_hour": 10,
            "end_hour": 12,
            "ministry_english_name": "Alpha 2026",
        },
        {
            "remark_suffix": "ministry-secondary2 basketball evening",
            "booker_email": DEMO_SECONDARY_2_USER_EMAIL,
            "room_codes": ["lobby"],
            "preferred_offset": 4,
            "start_hour": 18,
            "end_hour": 19,
            "ministry_english_name": "Basketball",
        },
        {
            "remark_suffix": "ministry-multi gym-lobby",
            "booker_email": DEMO_PRIMARY_USER_EMAIL,
            "room_codes": ["gym", "lobby"],
            "preferred_offset": 5,
            "start_hour": 17,
            "end_hour": 18,
            "ministry_english_name": "Pickleball",
        },
        {
            "remark_suffix": "personal-extra classroom-107",
            "booker_email": DEMO_PERSONAL_BOOKER_EMAILS[0],
            "room_codes": ["classroom-107"],
            "preferred_offset": 6,
            "start_hour": 13,
            "end_hour": 14,
        },
    ]
    plans: list[dict[str, Any]] = []
    for draft in drafts:
        room_codes = list(draft["room_codes"])
        day_offset = _shift_offset_off_blackouts(today=today, preferred_offset=draft["preferred_offset"], room_codes=room_codes)
        plans.append(
            _plan(
                remark_suffix=draft["remark_suffix"],
                booker_email=draft["booker_email"],
                room_codes=room_codes,
                day_offset=day_offset,
                start_hour=draft["start_hour"],
                end_hour=draft["end_hour"],
                ministry_english_name=draft.get("ministry_english_name"),
            )
        )
    return plans
