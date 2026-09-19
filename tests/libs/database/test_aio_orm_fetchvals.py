"""
Regression coverage for issue #216: fetchvals() stringified datetimes via
Converter.format_value, so callers that need real datetime.astimezone()
support (e.g. BookingRepository.list_rental_occurrence_starts) crashed with
`AttributeError: 'str' object has no attribute 'astimezone'`.
"""

from datetime import datetime, timezone

import pytest

from portal.libs.database.aio_orm import Session, _Select


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
async def test_fetchvals_default_still_stringifies_datetime():
    now = datetime(2026, 1, 6, 14, 0, 0, tzinfo=timezone.utc)
    session = _make_session([(now,)])

    result = await session.fetchvals("SELECT start_at FROM facility_booking")

    assert result == ["2026-01-06 14:00:00"]


@pytest.mark.asyncio
async def test_fetchvals_raw_returns_driver_native_datetime():
    now = datetime(2026, 1, 6, 14, 0, 0, tzinfo=timezone.utc)
    session = _make_session([(now,)])

    result = await session.fetchvals("SELECT start_at FROM facility_booking", raw=True)

    assert result == [now]
    assert result[0].astimezone(timezone.utc) == now


class _FakeQuery:
    def __init__(self, statement):
        self.statement = statement


@pytest.mark.asyncio
async def test_select_fetchvals_forwards_raw_flag_to_session():
    now = datetime(2026, 1, 6, 14, 0, 0, tzinfo=timezone.utc)
    session = _make_session([(now,)])
    select = _Select.__new__(_Select)
    select._select = _FakeQuery("SELECT start_at FROM facility_booking")
    select._session = session

    result = await select.fetchvals(raw=True)

    assert result == [now]
