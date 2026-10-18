"""
Pure Timetable cell / room-visibility / conflict-redaction projection helpers.

Authoritative cells and templates override AM/PM freelist inference. Personal
projections never receive Ministry occupancy identifiers or contacts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.domain.facility.constants import TIMETABLE_CELL_MINUTES, TIMETABLE_CELLS_PER_DAY, RecurringConflictKind, TimetableCellState, TimetableOccupancyKind


@dataclass(frozen=True)
class OpenInterval:
    """Facility-local open (non-Blackout template) interval in UTC."""

    start_at: datetime
    end_at: datetime


@dataclass(frozen=True)
class OccupancyInterval:
    """Effective occupancy overlapping a room day."""

    booking_id: UUID
    start_at: datetime
    end_at: datetime
    booking_start_at: datetime
    ministry_id: Optional[UUID] = None
    ministry_name: Optional[str] = None
    contact_display_name: Optional[str] = None
    contact_email: Optional[str] = None


@dataclass(frozen=True)
class ProjectedEvent:
    """Ministry-context Timetable event clipped to open non-Blackout time."""

    start_at: datetime
    end_at: datetime
    occupancy_kind: str
    is_overridable: bool
    ministry_name: Optional[str] = None
    contact_display_name: Optional[str] = None
    contact_email: Optional[str] = None
    booking_id: Optional[UUID] = None


def day_cell_bounds(day: date, tz: ZoneInfo) -> list[tuple[datetime, datetime]]:
    """Return 48 half-hour UTC bounds covering facility-local midnight to next midnight."""
    day_start = datetime.combine(day, time.min, tzinfo=tz).astimezone(timezone.utc)
    cells: list[tuple[datetime, datetime]] = []
    for index in range(TIMETABLE_CELLS_PER_DAY):
        start_at = day_start + timedelta(minutes=TIMETABLE_CELL_MINUTES * index)
        end_at = start_at + timedelta(minutes=TIMETABLE_CELL_MINUTES)
        cells.append((start_at, end_at))
    return cells


def intervals_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def clip_interval(start_at: datetime, end_at: datetime, windows: list[OpenInterval]) -> list[tuple[datetime, datetime]]:
    """Intersect [start_at, end_at) with open windows; return non-empty clipped segments."""
    clipped: list[tuple[datetime, datetime]] = []
    for window in windows:
        seg_start = max(start_at, window.start_at)
        seg_end = min(end_at, window.end_at)
        if seg_start < seg_end:
            clipped.append((seg_start, seg_end))
    return clipped


def open_portion_in_cell(cell_start: datetime, cell_end: datetime, open_windows: list[OpenInterval]) -> list[tuple[datetime, datetime]]:
    return clip_interval(cell_start, cell_end, open_windows)


def classify_cell(
    *, cell_start: datetime, cell_end: datetime, open_windows: list[OpenInterval], occupancies: list[OccupancyInterval], is_priority: bool, now_utc: datetime
) -> TimetableCellState:
    """Classify one half-hour cell. Closed wins when no open non-Blackout time remains."""
    open_parts = open_portion_in_cell(cell_start, cell_end, open_windows)
    if not open_parts:
        return TimetableCellState.CLOSED

    overlapping = [
        item for item in occupancies if any(intervals_overlap(part_start, part_end, item.start_at, item.end_at) for part_start, part_end in open_parts)
    ]
    if not overlapping:
        return TimetableCellState.AVAILABLE

    overridable = [item for item in overlapping if item.ministry_id is None and is_priority and item.booking_start_at > now_utc]
    if overridable and len(overridable) == len(overlapping):
        return TimetableCellState.OVERRIDE
    return TimetableCellState.UNAVAILABLE


def room_has_offered_time(open_windows: list[OpenInterval]) -> bool:
    return any(window.start_at < window.end_at for window in open_windows)


def room_has_usable_free_interval(cell_states: list[TimetableCellState]) -> bool:
    return any(state == TimetableCellState.AVAILABLE for state in cell_states)


def should_include_room(*, is_ministry_context: bool, open_windows: list[OpenInterval], cell_states: list[TimetableCellState]) -> bool:
    """Personal keeps rooms with free intervals; Ministry retains occupied rooms with offered time."""
    if not room_has_offered_time(open_windows):
        return False
    if is_ministry_context:
        return True
    return room_has_usable_free_interval(cell_states)


def merge_contiguous_free_slots(cell_bounds: list[tuple[datetime, datetime]], cell_states: list[TimetableCellState]) -> list[tuple[datetime, datetime]]:
    """Build AM/PM freelist from Available cells only (Override is never advertised as free)."""
    merged: list[tuple[datetime, datetime]] = []
    current_start: Optional[datetime] = None
    current_end: Optional[datetime] = None
    for (start_at, end_at), state in zip(cell_bounds, cell_states, strict=True):
        if state != TimetableCellState.AVAILABLE:
            if current_start is not None and current_end is not None:
                merged.append((current_start, current_end))
            current_start = None
            current_end = None
            continue
        if current_start is None:
            current_start = start_at
            current_end = end_at
        else:
            current_end = end_at
    if current_start is not None and current_end is not None:
        merged.append((current_start, current_end))
    return merged


def project_ministry_events(
    *, occupancies: list[OccupancyInterval], open_windows: list[OpenInterval], is_priority: bool, now_utc: datetime
) -> list[ProjectedEvent]:
    """Clip occupancy to open non-Blackout intervals; keep adjacent bookings distinct."""
    events: list[ProjectedEvent] = []
    for item in occupancies:
        clipped = clip_interval(item.start_at, item.end_at, open_windows)
        is_ministry = item.ministry_id is not None
        is_overridable = (not is_ministry) and is_priority and item.booking_start_at > now_utc
        kind = TimetableOccupancyKind.MINISTRY.value if is_ministry else TimetableOccupancyKind.RENTAL.value
        for seg_start, seg_end in clipped:
            events.append(
                ProjectedEvent(
                    start_at=seg_start,
                    end_at=seg_end,
                    occupancy_kind=kind,
                    is_overridable=is_overridable,
                    ministry_name=item.ministry_name if is_ministry else None,
                    contact_display_name=item.contact_display_name,
                    contact_email=item.contact_email,
                    booking_id=item.booking_id,
                )
            )
    events.sort(key=lambda event: (event.start_at, event.end_at, event.booking_id or UUID(int=0)))
    return events


def redact_conflict_for_personal(conflict_kind: str, ministry_id: Optional[UUID]) -> tuple[str, Optional[UUID], None, None]:
    """Normalize Ministry occupancy to generic occupancy for Personal projections."""
    if conflict_kind == RecurringConflictKind.MINISTRY.value or ministry_id is not None:
        return RecurringConflictKind.OCCUPANCY.value, None, None, None
    return conflict_kind, ministry_id, None, None


def format_local_hm(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%H:%M")
