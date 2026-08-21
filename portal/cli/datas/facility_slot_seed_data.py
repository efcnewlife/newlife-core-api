"""
Facility room slot template and blackout demo seed data.

Names use the ``seed:`` prefix so the seed command can replace only demo rows.
Slot templates are built per room code at seed time (every room in the database).
"""

from datetime import date, time
from typing import Any, Optional

from portal.domain.facility.constants import DayOfWeek, RoomBlackoutKind
from portal.domain.facility.days_of_week_mask import days_to_mask

SEED_NAME_PREFIX = "seed:"

ALL_DAYS = [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]

SUNDAY_MORNING_BLACKOUT_ROOM_CODES = ("sanctuary-hall", "gym", "lobby")

# Demo one-off dates (fixed calendar days for local Toronto wall clock).
CAMPUS_HOLIDAY_DEMO_DATE = date(2027, 1, 1)
SANCTUARY_MAINTENANCE_DEMO_DATE = date(2027, 1, 15)


def _slot(
    *, room_code: str, name: str, days_of_week: list[int], start_time: time, end_time: time, slot_duration_minutes: int = 60, is_active: bool = True
) -> dict[str, Any]:
    return {
        "room_code": room_code,
        "name": name if name.startswith(SEED_NAME_PREFIX) else f"{SEED_NAME_PREFIX}{name}",
        "days_of_week_mask": days_to_mask(days_of_week),
        "start_time": start_time,
        "end_time": end_time,
        "slot_duration_minutes": slot_duration_minutes,
        "is_active": is_active,
        "effective_from": None,
        "effective_to": None,
    }


def build_slot_template_rows_for_room_codes(room_codes: list[str]) -> list[dict[str, Any]]:
    """One all-week 08:00-22:00 template per room, 60-minute grid."""
    return [
        _slot(room_code=room_code, name="All-week daytime", days_of_week=ALL_DAYS, start_time=time(8, 0), end_time=time(22, 0), slot_duration_minutes=60)
        for room_code in room_codes
    ]


def _blackout(
    *,
    name: str,
    reason: str,
    kind: RoomBlackoutKind,
    start_time: time,
    end_time: time,
    room_code: Optional[str] = None,
    blackout_date: Optional[date] = None,
    days_of_week: Optional[list[int]] = None,
    is_active: bool = True,
    effective_from: Optional[date] = None,
    effective_to: Optional[date] = None,
) -> dict[str, Any]:
    seeded_name = name if name.startswith(SEED_NAME_PREFIX) else f"{SEED_NAME_PREFIX}{name}"
    if kind == RoomBlackoutKind.ONE_OFF:
        return {
            "room_code": room_code,
            "name": seeded_name,
            "reason": reason,
            "kind": kind.value,
            "blackout_date": blackout_date,
            "days_of_week_mask": None,
            "start_time": start_time,
            "end_time": end_time,
            "is_active": is_active,
            "effective_from": None,
            "effective_to": None,
        }
    return {
        "room_code": room_code,
        "name": seeded_name,
        "reason": reason,
        "kind": kind.value,
        "blackout_date": None,
        "days_of_week_mask": days_to_mask(days_of_week or []),
        "start_time": start_time,
        "end_time": end_time,
        "is_active": is_active,
        "effective_from": effective_from,
        "effective_to": effective_to,
    }


facility_blackout_seed_rows: list[dict[str, Any]] = [
    _blackout(
        room_code=None,
        name="Campus holiday demo",
        reason="Demo campus-wide holiday closure",
        kind=RoomBlackoutKind.ONE_OFF,
        blackout_date=CAMPUS_HOLIDAY_DEMO_DATE,
        start_time=time(0, 0),
        end_time=time(23, 59),
    ),
    _blackout(
        room_code="gym",
        name="Wednesday afternoon closed",
        reason="Demo weekly staff block on gym",
        kind=RoomBlackoutKind.RECURRING,
        days_of_week=[DayOfWeek.WEDNESDAY],
        start_time=time(14, 0),
        end_time=time(16, 0),
    ),
    _blackout(
        room_code="sanctuary-hall",
        name="Maintenance demo",
        reason="Demo afternoon maintenance window",
        kind=RoomBlackoutKind.ONE_OFF,
        blackout_date=SANCTUARY_MAINTENANCE_DEMO_DATE,
        start_time=time(13, 0),
        end_time=time(17, 0),
    ),
    *[
        _blackout(
            room_code=room_code,
            name=f"Sunday morning closed ({room_code})",
            reason="Demo Sunday morning Blackout",
            kind=RoomBlackoutKind.RECURRING,
            days_of_week=[DayOfWeek.SUNDAY],
            start_time=time(8, 0),
            end_time=time(13, 0),
        )
        for room_code in SUNDAY_MORNING_BLACKOUT_ROOM_CODES
    ],
]
