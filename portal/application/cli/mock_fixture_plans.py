"""
Near-term Mock fixture plans for `seed-mock-data`.

Booking scenarios keep the agreed personal/Ministry/multi-room distribution.
Slot templates and Blackouts carry a machine-readable `mock:` run marker in a
readable QA label. Placement searches the next 30 local days and never replaces
existing occupancy or Blackouts.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.cli.mock_user_persona import PERSONA_PERSONAL, PERSONA_STEWARD
from portal.domain.facility.constants import DayOfWeek, RoomBlackoutKind
from portal.domain.facility.days_of_week_mask import days_to_mask

MOCK_RUN_MARKER_PREFIX = "mock:"
BOOKING_PLACEMENT_WINDOW_DAYS = 30
MOCK_FIXTURE_TIMEZONE = ZoneInfo("America/Toronto")
ALL_DAYS = [DayOfWeek.MONDAY, DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY, DayOfWeek.THURSDAY, DayOfWeek.FRIDAY, DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]
SLOT_TEMPLATE_LABEL = "all-week daytime"
CAMPUS_BLACKOUT_LABEL = "campus holiday"
ROOM_BLACKOUT_LABEL = "sanctuary maintenance"
ROOM_BLACKOUT_ROOM_CODE = "sanctuary-hall"
CAMPUS_BLACKOUT_START = time(0, 0)
CAMPUS_BLACKOUT_END = time(23, 59)
ROOM_BLACKOUT_START = time(13, 0)
ROOM_BLACKOUT_END = time(17, 0)


def mock_run_marker(run_identity: str) -> str:
    """Return the machine-readable `mock:<run identity>` marker."""
    return f"{MOCK_RUN_MARKER_PREFIX}{run_identity}"


def mock_fixture_name(label: str, run_identity: str) -> str:
    """Return a readable QA label that still carries the Mock run marker."""
    return f"Mock {label} ({mock_run_marker(run_identity)})"


@dataclass(frozen=True)
class MockBookingPlan:
    """One confirmed near-term Booking scenario before dates are placed."""

    title: str
    booker_persona: str
    booker_index: int
    room_codes: tuple[str, ...]
    start_hour: int
    end_hour: int
    ministry_label: Optional[str]


@dataclass(frozen=True)
class OccupyingInterval:
    """One existing or already-placed room occupancy interval (UTC)."""

    facility_id: UUID
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class ExistingBlackout:
    """One persisted Blackout used when searching for a free scenario slot."""

    facility_id: Optional[UUID]
    kind: str
    blackout_date: Optional[date]
    days_of_week_mask: Optional[int]
    start_time: time
    end_time: time
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


@dataclass(frozen=True)
class PlacedBooking:
    """One Mock Booking after a local calendar day has been chosen."""

    plan: MockBookingPlan
    local_day: date
    start_at: datetime
    end_at: datetime


def build_mock_booking_plans() -> list[MockBookingPlan]:
    """Return the ten confirmed Booking scenarios (six personal, four Ministry)."""
    return [
        MockBookingPlan("Personal classroom 105", PERSONA_PERSONAL, 0, ("classroom-105",), 10, 11, None),
        MockBookingPlan("Personal classroom 106", PERSONA_PERSONAL, 1, ("classroom-106",), 11, 12, None),
        MockBookingPlan("Personal lounge", PERSONA_PERSONAL, 2, ("lounge",), 14, 15, None),
        MockBookingPlan("Personal meeting room", PERSONA_PERSONAL, 3, ("meeting-room",), 15, 16, None),
        MockBookingPlan("Personal nursery", PERSONA_PERSONAL, 4, ("nursery",), 10, 11, None),
        MockBookingPlan("Personal classroom 107", PERSONA_PERSONAL, 0, ("classroom-107",), 13, 14, None),
        MockBookingPlan("Badminton gym", PERSONA_STEWARD, 0, ("gym",), 18, 19, "Badminton"),
        MockBookingPlan("Alpha classroom 125", PERSONA_STEWARD, 1, ("classroom-125",), 10, 12, "Alpha"),
        MockBookingPlan("Basketball lobby", PERSONA_STEWARD, 2, ("lobby",), 18, 19, "Basketball"),
        MockBookingPlan("Pickleball gym lobby", PERSONA_STEWARD, 0, ("gym", "lobby"), 17, 18, "Pickleball"),
    ]


def local_range_to_utc(*, local_day: date, start_hour: int, end_hour: int, tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE) -> tuple[datetime, datetime]:
    """Convert a facility-local wall-clock range on `local_day` to UTC."""
    start_local = datetime(local_day.year, local_day.month, local_day.day, start_hour, 0, tzinfo=tz)
    end_local = datetime(local_day.year, local_day.month, local_day.day, end_hour, 0, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def local_times_to_utc(*, local_day: date, start_time: time, end_time: time, tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE) -> tuple[datetime, datetime]:
    """Convert a facility-local timed range on `local_day` to UTC."""
    start_local = datetime(local_day.year, local_day.month, local_day.day, start_time.hour, start_time.minute, tzinfo=tz)
    end_local = datetime(local_day.year, local_day.month, local_day.day, end_time.hour, end_time.minute, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _candidate_days(today: date) -> list[date]:
    return [today + timedelta(days=offset) for offset in range(1, BOOKING_PLACEMENT_WINDOW_DAYS + 1)]


def _times_overlap(left_start: time, left_end: time, right_start: time, right_end: time) -> bool:
    return left_start < right_end and right_start < left_end


def _intervals_overlap(left_start: datetime, left_end: datetime, right_start: datetime, right_end: datetime) -> bool:
    return left_start < right_end and right_start < left_end


def _blackout_applies_on_date(blackout: ExistingBlackout, day: date) -> bool:
    if blackout.kind == RoomBlackoutKind.ONE_OFF.value:
        return blackout.blackout_date == day
    if blackout.days_of_week_mask is None:
        return False
    if blackout.effective_from is not None and day < blackout.effective_from:
        return False
    if blackout.effective_to is not None and day > blackout.effective_to:
        return False
    return (blackout.days_of_week_mask & (1 << day.weekday())) != 0


def _blackout_covers_room(blackout: ExistingBlackout, facility_id: UUID) -> bool:
    return blackout.facility_id is None or blackout.facility_id == facility_id


def blackout_overlaps_interval(
    blackout: ExistingBlackout, *, facility_ids: list[UUID], start_at: datetime, end_at: datetime, tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE
) -> bool:
    """Return True when the Blackout closes any of `facility_ids` during [start_at, end_at)."""
    local_start = start_at.astimezone(tz)
    local_end = end_at.astimezone(tz)
    day = local_start.date()
    if not _blackout_applies_on_date(blackout, day):
        return False
    if not any(_blackout_covers_room(blackout, facility_id) for facility_id in facility_ids):
        return False
    return _times_overlap(local_start.time(), local_end.time(), blackout.start_time, blackout.end_time)


def occupancy_overlaps_interval(occupancy: list[OccupyingInterval], *, facility_ids: list[UUID], start_at: datetime, end_at: datetime) -> bool:
    """Return True when any confirmed occupancy overlaps the requested room interval."""
    wanted = set(facility_ids)
    return any(item.facility_id in wanted and _intervals_overlap(item.start_at, item.end_at, start_at, end_at) for item in occupancy)


def _interval_is_free(
    *, facility_ids: list[UUID], start_at: datetime, end_at: datetime, occupancy: list[OccupyingInterval], blackouts: list[ExistingBlackout], tz: ZoneInfo
) -> bool:
    if occupancy_overlaps_interval(occupancy, facility_ids=facility_ids, start_at=start_at, end_at=end_at):
        return False
    return not any(blackout_overlaps_interval(blackout, facility_ids=facility_ids, start_at=start_at, end_at=end_at, tz=tz) for blackout in blackouts)


def place_campus_blackout(
    *, today: date, occupancy: list[OccupyingInterval], blackouts: list[ExistingBlackout], all_facility_ids: list[UUID], tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE
) -> Optional[date]:
    """Return the first free local day in the 30-day window for a campus-wide Blackout."""
    for local_day in _candidate_days(today):
        start_at, end_at = local_times_to_utc(local_day=local_day, start_time=CAMPUS_BLACKOUT_START, end_time=CAMPUS_BLACKOUT_END, tz=tz)
        if _interval_is_free(facility_ids=all_facility_ids, start_at=start_at, end_at=end_at, occupancy=occupancy, blackouts=blackouts, tz=tz):
            return local_day
    return None


def place_room_blackout(
    *,
    today: date,
    occupancy: list[OccupyingInterval],
    blackouts: list[ExistingBlackout],
    facility_id: UUID,
    excluded_dates: set[date],
    tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE,
) -> Optional[date]:
    """Return the first free local day in the 30-day window for the room-specific Blackout."""
    for local_day in _candidate_days(today):
        if local_day in excluded_dates:
            continue
        start_at, end_at = local_times_to_utc(local_day=local_day, start_time=ROOM_BLACKOUT_START, end_time=ROOM_BLACKOUT_END, tz=tz)
        if _interval_is_free(facility_ids=[facility_id], start_at=start_at, end_at=end_at, occupancy=occupancy, blackouts=blackouts, tz=tz):
            return local_day
    return None


def place_booking_plan(
    plan: MockBookingPlan,
    *,
    today: date,
    occupancy: list[OccupyingInterval],
    blackouts: list[ExistingBlackout],
    facility_ids: list[UUID],
    tz: ZoneInfo = MOCK_FIXTURE_TIMEZONE,
) -> Optional[PlacedBooking]:
    """Return the first 30-day slot that keeps this scenario's rooms, hours, and duration."""
    for local_day in _candidate_days(today):
        start_at, end_at = local_range_to_utc(local_day=local_day, start_hour=plan.start_hour, end_hour=plan.end_hour, tz=tz)
        if _interval_is_free(facility_ids=facility_ids, start_at=start_at, end_at=end_at, occupancy=occupancy, blackouts=blackouts, tz=tz):
            return PlacedBooking(plan=plan, local_day=local_day, start_at=start_at, end_at=end_at)
    return None


def slot_template_mask() -> int:
    """Return the all-week bitmask used by Mock weekly slot templates."""
    return days_to_mask(ALL_DAYS)
