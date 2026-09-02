"""
Booking line validation unit tests.
"""

from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.booking_line_validation import ResolvedBookingLine, envelope_interval, primary_facility_id, validate_booking_lines
from portal.exceptions.responses import BadRequestException

TORONTO = ZoneInfo("America/Toronto")


def _line(facility_id, start_at, end_at, sequence=0) -> ResolvedBookingLine:
    return ResolvedBookingLine(facility_id=facility_id, start_at=start_at, end_at=end_at, sequence=sequence)


def test_envelope_interval_uses_min_start_and_max_end():
    room_id = uuid4()
    lines = [
        _line(room_id, datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc), datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc), sequence=1),
        _line(room_id, datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc), datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc), sequence=0),
    ]
    start, end = envelope_interval(lines)
    assert start == datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)


def test_primary_facility_id_uses_lowest_sequence():
    first_room = uuid4()
    second_room = uuid4()
    lines = [
        _line(second_room, datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc), datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc), sequence=1),
        _line(first_room, datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc), datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc), sequence=0),
    ]
    assert primary_facility_id(lines) == first_room


def test_validate_booking_lines_rejects_cross_midnight():
    room_id = uuid4()
    lines = [_line(room_id, datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc), datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc))]
    with pytest.raises(BadRequestException) as exc_info:
        validate_booking_lines(lines, TORONTO)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINE_CROSS_MIDNIGHT"


def test_validate_booking_lines_rejects_different_calendar_days():
    room_id = uuid4()
    lines = [
        _line(room_id, datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc), datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc), sequence=0),
        _line(room_id, datetime(2026, 5, 2, 14, 0, tzinfo=timezone.utc), datetime(2026, 5, 2, 16, 0, tzinfo=timezone.utc), sequence=1),
    ]
    with pytest.raises(BadRequestException) as exc_info:
        validate_booking_lines(lines, TORONTO)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINES_NOT_SAME_DAY"


def test_validate_booking_lines_rejects_exact_duplicate():
    room_id = uuid4()
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    lines = [_line(room_id, start, end, sequence=0), _line(room_id, start, end, sequence=1)]
    with pytest.raises(BadRequestException) as exc_info:
        validate_booking_lines(lines, TORONTO)
    assert exc_info.value.error_code == "FACILITY_BOOKING_DUPLICATE_LINE"
