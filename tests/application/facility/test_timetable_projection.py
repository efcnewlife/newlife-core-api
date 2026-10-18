"""
Pure Timetable projection helpers (cell states, visibility, Personal redaction).
"""

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

from portal.application.facility.timetable_projection import (
    OccupancyInterval,
    OpenInterval,
    classify_cell,
    day_cell_bounds,
    merge_contiguous_free_slots,
    project_ministry_events,
    redact_conflict_for_personal,
    should_include_room,
)
from portal.domain.facility.constants import TIMETABLE_CELLS_PER_DAY, RecurringConflictKind, TimetableCellState, TimetableOccupancyKind

TZ = ZoneInfo("America/Toronto")


def _utc(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ).astimezone(timezone.utc)


def test_day_cell_bounds_are_48_half_hours():
    day = date(2026, 7, 20)
    cells = day_cell_bounds(day, TZ)
    assert len(cells) == TIMETABLE_CELLS_PER_DAY
    assert cells[0][0].astimezone(TZ).time() == time(0, 0)
    assert cells[-1][1].astimezone(TZ).time() == time(0, 0)
    assert (cells[0][1] - cells[0][0]).total_seconds() == 30 * 60


def test_classify_closed_outside_template_and_blackout():
    day = date(2026, 7, 20)
    open_windows = [OpenInterval(_utc(day, 9), _utc(day, 12))]
    cell_start, cell_end = _utc(day, 8, 0), _utc(day, 8, 30)
    assert classify_cell(cell_start=cell_start, cell_end=cell_end, open_windows=open_windows, occupancies=[], is_priority=False, now_utc=_utc(day, 0)) == (
        TimetableCellState.CLOSED
    )
    # Blackout removes open window for 10:00-11:00
    open_without_blackout = [OpenInterval(_utc(day, 9), _utc(day, 10)), OpenInterval(_utc(day, 11), _utc(day, 12))]
    assert (
        classify_cell(
            cell_start=_utc(day, 10), cell_end=_utc(day, 10, 30), open_windows=open_without_blackout, occupancies=[], is_priority=False, now_utc=_utc(day, 0)
        )
        == TimetableCellState.CLOSED
    )


def test_classify_available_and_partial_occupancy_cell():
    day = date(2026, 7, 20)
    open_windows = [OpenInterval(_utc(day, 9), _utc(day, 12))]
    now = _utc(day, 0)
    assert (
        classify_cell(cell_start=_utc(day, 9), cell_end=_utc(day, 9, 30), open_windows=open_windows, occupancies=[], is_priority=False, now_utc=now)
        == TimetableCellState.AVAILABLE
    )
    rental = OccupancyInterval(booking_id=uuid4(), start_at=_utc(day, 9, 15), end_at=_utc(day, 9, 45), booking_start_at=_utc(day, 9, 15))
    assert (
        classify_cell(cell_start=_utc(day, 9), cell_end=_utc(day, 9, 30), open_windows=open_windows, occupancies=[rental], is_priority=False, now_utc=now)
        == TimetableCellState.UNAVAILABLE
    )


def test_classify_override_only_for_priority_future_rental():
    day = date(2026, 7, 20)
    open_windows = [OpenInterval(_utc(day, 9), _utc(day, 12))]
    now = _utc(day, 8)
    rental = OccupancyInterval(booking_id=uuid4(), start_at=_utc(day, 10), end_at=_utc(day, 11), booking_start_at=_utc(day, 10))
    assert (
        classify_cell(cell_start=_utc(day, 10), cell_end=_utc(day, 10, 30), open_windows=open_windows, occupancies=[rental], is_priority=True, now_utc=now)
        == TimetableCellState.OVERRIDE
    )
    assert (
        classify_cell(cell_start=_utc(day, 10), cell_end=_utc(day, 10, 30), open_windows=open_windows, occupancies=[rental], is_priority=False, now_utc=now)
        == TimetableCellState.UNAVAILABLE
    )
    started = OccupancyInterval(booking_id=uuid4(), start_at=_utc(day, 7), end_at=_utc(day, 11), booking_start_at=_utc(day, 7))
    assert (
        classify_cell(cell_start=_utc(day, 10), cell_end=_utc(day, 10, 30), open_windows=open_windows, occupancies=[started], is_priority=True, now_utc=now)
        == TimetableCellState.UNAVAILABLE
    )


def test_classify_ministry_occupancy_never_override():
    day = date(2026, 7, 20)
    open_windows = [OpenInterval(_utc(day, 9), _utc(day, 12))]
    ministry = OccupancyInterval(booking_id=uuid4(), start_at=_utc(day, 10), end_at=_utc(day, 11), booking_start_at=_utc(day, 10), ministry_id=uuid4())
    assert (
        classify_cell(
            cell_start=_utc(day, 10), cell_end=_utc(day, 10, 30), open_windows=open_windows, occupancies=[ministry], is_priority=True, now_utc=_utc(day, 0)
        )
        == TimetableCellState.UNAVAILABLE
    )


def test_room_visibility_personal_vs_ministry():
    open_windows = [OpenInterval(_utc(date(2026, 7, 20), 9), _utc(date(2026, 7, 20), 12))]
    all_unavailable = [TimetableCellState.UNAVAILABLE] * 48
    mixed = [TimetableCellState.CLOSED] * 20 + [TimetableCellState.AVAILABLE] + [TimetableCellState.CLOSED] * 27
    assert should_include_room(is_ministry_context=False, open_windows=open_windows, cell_states=all_unavailable) is False
    assert should_include_room(is_ministry_context=True, open_windows=open_windows, cell_states=all_unavailable) is True
    assert should_include_room(is_ministry_context=False, open_windows=open_windows, cell_states=mixed) is True
    assert should_include_room(is_ministry_context=False, open_windows=[], cell_states=mixed) is False


def test_merge_contiguous_free_slots_excludes_override():
    day = date(2026, 7, 20)
    bounds = [(_utc(day, 9), _utc(day, 9, 30)), (_utc(day, 9, 30), _utc(day, 10)), (_utc(day, 10), _utc(day, 10, 30))]
    states = [TimetableCellState.AVAILABLE, TimetableCellState.OVERRIDE, TimetableCellState.AVAILABLE]
    merged = merge_contiguous_free_slots(bounds, states)
    assert merged == [(_utc(day, 9), _utc(day, 9, 30)), (_utc(day, 10), _utc(day, 10, 30))]


def test_project_ministry_events_clips_and_keeps_contacts_distinct():
    day = date(2026, 7, 20)
    open_windows = [OpenInterval(_utc(day, 9), _utc(day, 12))]
    first_id = uuid4()
    second_id = uuid4()
    ministry_id = uuid4()
    occupancies = [
        OccupancyInterval(
            booking_id=first_id,
            start_at=_utc(day, 8, 30),
            end_at=_utc(day, 10),
            booking_start_at=_utc(day, 8, 30),
            ministry_id=ministry_id,
            ministry_name="Youth",
            contact_display_name="Pat Steward",
            contact_email="pat@efcnewlife.org",
        ),
        OccupancyInterval(
            booking_id=second_id,
            start_at=_utc(day, 10),
            end_at=_utc(day, 11),
            booking_start_at=_utc(day, 10),
            contact_display_name="Jane Booker",
            contact_email="jane@example.com",
        ),
    ]
    events = project_ministry_events(occupancies=occupancies, open_windows=open_windows, is_priority=False, now_utc=_utc(day, 0))
    assert len(events) == 2
    assert events[0].start_at == _utc(day, 9)
    assert events[0].end_at == _utc(day, 10)
    assert events[0].occupancy_kind == TimetableOccupancyKind.MINISTRY.value
    assert events[0].ministry_name == "Youth"
    assert events[0].contact_display_name == "Pat Steward"
    assert events[0].is_overridable is False
    assert events[1].occupancy_kind == TimetableOccupancyKind.RENTAL.value
    assert events[1].contact_email == "jane@example.com"
    assert events[1].ministry_name is None


def test_redact_conflict_for_personal_normalizes_ministry():
    ministry_id = uuid4()
    kind, mid, steward_name, steward_email = redact_conflict_for_personal(RecurringConflictKind.MINISTRY.value, ministry_id)
    assert kind == RecurringConflictKind.OCCUPANCY.value
    assert mid is None
    assert steward_name is None
    assert steward_email is None
