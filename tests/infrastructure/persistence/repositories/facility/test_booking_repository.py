"""
Regression coverage for issue #216: BookingRepository.list_rental_occurrence_starts
is typed `-> list[datetime]` and its caller (RecurringBookingService.
_weekly_quota_conflict_dates) calls `.astimezone()` on every item. Before the fix,
fetchvals() ran results through Converter.format_value, silently turning the
driver's real datetimes into "%Y-%m-%d %H:%M:%S" strings, which crashed with
`AttributeError: 'str' object has no attribute 'astimezone'` whenever the booker
had a pre-existing occurrence in the queried range.
"""

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
