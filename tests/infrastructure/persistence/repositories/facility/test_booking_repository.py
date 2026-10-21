"""
Regression coverage for issue #216: BookingRepository.list_rental_occurrence_starts
is typed `-> list[datetime]` and its caller (RecurringBookingService.
_weekly_quota_conflict_dates) calls `.astimezone()` on every item. Before the fix,
fetchvals() ran results through Converter.format_value, silently turning the
driver's real datetimes into "%Y-%m-%d %H:%M:%S" strings, which crashed with
`AttributeError: 'str' object has no attribute 'astimezone'` whenever the booker
had a pre-existing occurrence in the queried range.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.libs.database.aio_orm import Session


class _FakeConnection:
    def __init__(self, rows: list[tuple]):
        self._rows = rows

    async def fetch(self, sql, *params, timeout=None):
        return self._rows


def _make_session(rows: list[tuple]) -> Session:
    session = Session.__new__(Session)
    session._conn = _FakeConnection(rows)
    session._echo = False
    session._locker = asyncio.Lock()

    async def _noop_ensure_connection(lock: bool = True):
        return None

    session._ensure_connection = _noop_ensure_connection
    return session


@pytest.mark.asyncio
async def test_list_rental_occurrence_starts_returns_astimezone_capable_datetimes():
    existing_start = datetime(2026, 1, 6, 14, 0, 0, tzinfo=timezone.utc)
    session = _make_session([(existing_start,)])
    repository = BookingRepository(session)

    starts = await repository.list_rental_occurrence_starts(uuid4(), datetime(2026, 1, 4, tzinfo=timezone.utc), datetime(2026, 1, 11, tzinfo=timezone.utc))

    assert starts == [existing_start]
    assert starts[0].astimezone(timezone.utc) == existing_start


@pytest.mark.asyncio
async def test_list_rental_occurrence_starts_empty_when_no_rows():
    session = _make_session([])
    repository = BookingRepository(session)

    starts = await repository.list_rental_occurrence_starts(uuid4(), datetime(2026, 1, 4, tzinfo=timezone.utc), datetime(2026, 1, 11, tzinfo=timezone.utc))

    assert starts == []


@pytest.mark.asyncio
async def test_list_occupying_slots_returns_tz_aware_utc_datetimes():
    # Issue #241 / EFC-264: naive datetimes here crashed room availability with
    # `TypeError: can't compare offset-naive and offset-aware datetimes`.
    start_at = datetime(2026, 10, 23, 14, 0, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 10, 23, 15, 0, 0, tzinfo=timezone.utc)
    facility_id = uuid4()
    row = {
        "id": uuid4(),
        "user_id": uuid4(),
        "ministry_id": None,
        "ministry_name": None,
        "facility_id": facility_id,
        "start_at": start_at,
        "end_at": end_at,
        "booker_email": "booker@example.com",
        "booker_display_name": "Booker",
    }
    session = _make_session([row])
    repository = BookingRepository(session)

    occupying = await repository.list_occupying_slots(facility_id, datetime(2026, 10, 23, tzinfo=timezone.utc), datetime(2026, 10, 24, tzinfo=timezone.utc))

    assert len(occupying) == 1
    assert occupying[0].start_at.tzinfo is not None
    assert occupying[0].end_at.tzinfo is not None
    assert occupying[0].start_at == start_at
    assert occupying[0].end_at == end_at
