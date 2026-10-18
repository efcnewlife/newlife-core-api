"""
Pure member opening-hours validation against Room Slot Templates.
"""

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.opening_hours import member_interval_within_opening_hours, raise_if_outside_opening_hours
from portal.application.facility.results import RoomSlotTemplateResult
from portal.domain.facility.constants import BookingErrorCode
from portal.exceptions.responses import BadRequestException

TORONTO = ZoneInfo("America/Toronto")
DAY = date(2026, 7, 20)  # Monday


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(DAY, time(hour, minute), tzinfo=TORONTO).astimezone(timezone.utc)


def _template(
    *, start: time = time(9, 0), end: time = time(12, 0), duration: int = 60, effective_from: date | None = None, effective_to: date | None = None
) -> RoomSlotTemplateResult:
    return RoomSlotTemplateResult(
        id=uuid4(),
        facility_id=uuid4(),
        name="Morning",
        days_of_week_mask=127,
        start_time=start,
        end_time=end,
        slot_duration_minutes=duration,
        is_active=True,
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_accepts_interval_inside_template_meeting_minimum_duration():
    templates = [_template(start=time(9, 0), end=time(12, 0), duration=60)]
    assert member_interval_within_opening_hours(_utc(9, 30), _utc(10, 30), templates, TORONTO)


def test_accepts_longer_interval_without_requiring_duration_multiples():
    templates = [_template(start=time(9, 0), end=time(17, 0), duration=60)]
    assert member_interval_within_opening_hours(_utc(9, 0), _utc(10, 30), templates, TORONTO)


def test_rejects_interval_shorter_than_template_minimum():
    templates = [_template(start=time(9, 0), end=time(12, 0), duration=60)]
    assert not member_interval_within_opening_hours(_utc(9, 0), _utc(9, 30), templates, TORONTO)


def test_rejects_interval_with_no_applicable_template():
    assert not member_interval_within_opening_hours(_utc(9, 0), _utc(10, 0), [], TORONTO)


def test_rejects_interval_outside_template_window():
    templates = [_template(start=time(9, 0), end=time(12, 0), duration=60)]
    assert not member_interval_within_opening_hours(_utc(13, 0), _utc(14, 0), templates, TORONTO)


def test_rejects_interval_crossing_closed_gap_between_templates():
    templates = [_template(start=time(9, 0), end=time(12, 0), duration=60), _template(start=time(13, 0), end=time(17, 0), duration=60)]
    assert not member_interval_within_opening_hours(_utc(11, 0), _utc(14, 0), templates, TORONTO)


def test_accepts_interval_across_adjacent_templates_without_gap():
    templates = [_template(start=time(9, 0), end=time(12, 0), duration=60), _template(start=time(12, 0), end=time(17, 0), duration=60)]
    assert member_interval_within_opening_hours(_utc(11, 0), _utc(13, 0), templates, TORONTO)


def test_rejects_template_outside_effective_dates():
    templates = [_template(start=time(9, 0), end=time(17, 0), duration=60, effective_from=date(2027, 1, 1))]
    assert not member_interval_within_opening_hours(_utc(10, 0), _utc(11, 0), templates, TORONTO)


def test_raise_if_outside_opening_hours_uses_stable_error_code():
    facility_id = uuid4()
    with pytest.raises(BadRequestException) as exc_info:
        raise_if_outside_opening_hours(facility_id=facility_id, start_at=_utc(6, 0), end_at=_utc(7, 0), templates=[_template()], local_tz=TORONTO)
    assert exc_info.value.error_code == BookingErrorCode.OUTSIDE_OPENING_HOURS.value
    assert exc_info.value.context["facility_id"] == str(facility_id)
