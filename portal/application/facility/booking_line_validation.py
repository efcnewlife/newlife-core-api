"""
Shared validation for booking room lines (create/update).
"""

from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.commands import BookingRoomLineCommand
from portal.domain.facility.constants import FacilityErrorCode
from portal.exceptions.responses import BadRequestException


class ResolvedBookingLine:
    """A booking line with resolved UTC interval and display order."""

    __slots__ = ("facility_id", "start_at", "end_at", "sequence")

    def __init__(self, facility_id: UUID, start_at: datetime, end_at: datetime, sequence: int):
        self.facility_id = facility_id
        self.start_at = start_at
        self.end_at = end_at
        self.sequence = sequence


def resolve_booking_lines(rooms: list[BookingRoomLineCommand], header_start: datetime, header_end: datetime) -> list[ResolvedBookingLine]:
    """Resolve per-line intervals, falling back to header times when a line omits them."""
    return [
        ResolvedBookingLine(facility_id=line.facility_id, start_at=line.start_at or header_start, end_at=line.end_at or header_end, sequence=line.sequence)
        for line in rooms
    ]


def envelope_interval(lines: list[ResolvedBookingLine]) -> tuple[datetime, datetime]:
    """Earliest line start and latest line end."""
    return min(line.start_at for line in lines), max(line.end_at for line in lines)


def primary_facility_id(lines: list[ResolvedBookingLine]) -> UUID:
    """Primary facility is the lowest sequence line."""
    return min(lines, key=lambda line: line.sequence).facility_id


def validate_booking_lines(lines: list[ResolvedBookingLine], local_tz: ZoneInfo) -> None:
    """Enforce same local calendar day, no cross-midnight, no exact duplicates, end > start."""
    calendar_days: set[date] = set()
    seen: set[tuple[UUID, datetime, datetime]] = set()

    for line in lines:
        if line.end_at <= line.start_at:
            raise BadRequestException(detail="end_at must be after start_at", error_code=FacilityErrorCode.BOOKING_INVALID_TIME_RANGE.value)

        start_local = line.start_at.astimezone(local_tz)
        end_local = line.end_at.astimezone(local_tz)
        if start_local.date() != end_local.date():
            raise BadRequestException(detail="Booking line must not cross local midnight", error_code=FacilityErrorCode.BOOKING_LINE_CROSS_MIDNIGHT.value)

        calendar_days.add(start_local.date())

        line_key = (line.facility_id, line.start_at, line.end_at)
        if line_key in seen:
            raise BadRequestException(detail="Duplicate booking line", error_code=FacilityErrorCode.BOOKING_DUPLICATE_LINE.value)
        seen.add(line_key)

    if len(calendar_days) > 1:
        raise BadRequestException(
            detail="All booking lines must fall on the same local calendar day", error_code=FacilityErrorCode.BOOKING_LINES_NOT_SAME_DAY.value
        )
