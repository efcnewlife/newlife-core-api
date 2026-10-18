"""
Member opening-hours validation against Room Slot Templates.

Administrator create paths skip this check; occupancy and Blackout stay separate.
"""

from datetime import date, datetime, time
from typing import Optional, Sequence
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.results import RoomSlotTemplateResult
from portal.domain.facility.constants import BookingErrorCode
from portal.exceptions.responses import BadRequestException


def filter_applicable_templates(templates: Sequence[RoomSlotTemplateResult], day: date) -> list[RoomSlotTemplateResult]:
    """Keep templates whose effective date range includes ``day``."""
    applicable: list[RoomSlotTemplateResult] = []
    for template in templates:
        if template.effective_from and day < template.effective_from:
            continue
        if template.effective_to and day > template.effective_to:
            continue
        applicable.append(template)
    return applicable


def _combine_local(day: date, value: time, tz: ZoneInfo) -> datetime:
    return datetime.combine(day, value, tzinfo=tz)


def _merge_open_windows(windows: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not windows:
        return []
    ordered = sorted(windows, key=lambda item: item[0])
    merged: list[tuple[datetime, datetime]] = [ordered[0]]
    for start_at, end_at in ordered[1:]:
        prev_start, prev_end = merged[-1]
        if start_at <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end_at))
        else:
            merged.append((start_at, end_at))
    return merged


def _template_containing_start(templates: Sequence[RoomSlotTemplateResult], start_at: datetime, local_tz: ZoneInfo) -> Optional[RoomSlotTemplateResult]:
    start_time = start_at.astimezone(local_tz).time()
    for template in templates:
        if template.start_time <= start_time < template.end_time:
            return template
    return None


def member_interval_within_opening_hours(start_at: datetime, end_at: datetime, templates: Sequence[RoomSlotTemplateResult], local_tz: ZoneInfo) -> bool:
    """
    True when the complete interval lies in one contiguous template open window
    and lasts at least the start-cell template's slot_duration_minutes.
    """
    if end_at <= start_at:
        return False

    day = start_at.astimezone(local_tz).date()
    applicable = filter_applicable_templates(templates, day)
    if not applicable:
        return False

    start_template = _template_containing_start(applicable, start_at, local_tz)
    if start_template is None:
        return False

    duration_minutes = (end_at - start_at).total_seconds() / 60.0
    if duration_minutes < start_template.slot_duration_minutes:
        return False

    raw_windows = [
        (_combine_local(day, template.start_time, local_tz), _combine_local(day, template.end_time, local_tz))
        for template in applicable
        if template.start_time < template.end_time
    ]
    merged = _merge_open_windows(raw_windows)
    start_local = start_at.astimezone(local_tz)
    end_local = end_at.astimezone(local_tz)
    for window_start, window_end in merged:
        if window_start <= start_local and end_local <= window_end:
            return True
    return False


def raise_if_outside_opening_hours(
    *, facility_id: UUID, start_at: datetime, end_at: datetime, templates: Sequence[RoomSlotTemplateResult], local_tz: ZoneInfo
) -> None:
    """Raise FACILITY_BOOKING_OUTSIDE_OPENING_HOURS when the member interval is invalid."""
    if member_interval_within_opening_hours(start_at, end_at, templates, local_tz):
        return
    raise BadRequestException(
        detail=f"Room {facility_id} is outside opening hours for the selected time",
        error_code=BookingErrorCode.OUTSIDE_OPENING_HOURS.value,
        context={"facility_id": str(facility_id)},
    )
