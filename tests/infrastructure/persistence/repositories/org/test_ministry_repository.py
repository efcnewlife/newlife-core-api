"""
Regression coverage for EFC-248: Ministry list reads joined only the requested-locale
translation before `ministry_name_fallback` aggregated names, so a Ministry whose only
translation is in another locale (or any read with no resolved locale) came back with
`name: null`.

The repository SQL is compiled exactly as in production and executed against an
in-memory SQLite database. This does not replace PostgreSQL integration coverage.
"""

import asyncio
import re
import sqlite3
from collections.abc import Iterator
from uuid import UUID, uuid4

import pytest

from portal.application.org.commands import StewardDirectoryQueryCommand
from portal.application.org.mappers import ministry_list_to_api
from portal.application.org.results import MinistryListResult
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.database.aio_orm import Session

REPORTED_MINISTRY_ID = UUID("ca84b2e4-4a32-4ae4-84b4-ca401b4f4e71")
REPORTED_LOCALE_ID = UUID("019dd0c8-7540-7601-bfd1-7939ce75c16a")
DEFAULT_LOCALE_ID = uuid4()
OTHER_LOCALE_ID = uuid4()
USER_ID = uuid4()

_SCHEMA = """
CREATE TABLE public.system_locale (id TEXT PRIMARY KEY, is_default BOOLEAN NOT NULL, is_deleted BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE org.ministry (
    id TEXT PRIMARY KEY, status TEXT NOT NULL, has_priority_booking BOOLEAN NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT 1, is_deleted BOOLEAN NOT NULL DEFAULT 0, sequence REAL NOT NULL,
    created_at TEXT, updated_at TEXT
);
CREATE TABLE org.ministry_translation (id TEXT PRIMARY KEY, ministry_id TEXT NOT NULL, locale_id TEXT NOT NULL, name TEXT NOT NULL);
CREATE TABLE org.ministry_member (id TEXT PRIMARY KEY, ministry_id TEXT NOT NULL, user_id TEXT NOT NULL, member_role TEXT NOT NULL);
"""


class _SqliteConnection:
    """Executes asyncpg-style SQL compiled by the repository against SQLite."""

    def __init__(self, db: sqlite3.Connection):
        self._db = db

    def _run(self, sql: str, params: tuple):
        sql = re.sub(r"::\w+", "", sql)
        sql = re.sub(r"\$(\d+)", r"?\1", sql)
        params = tuple(str(p) if isinstance(p, UUID) else p for p in params)
        return self._db.execute(sql, params)

    async def fetch(self, sql, *params, timeout=None):
        return [dict(row) for row in self._run(sql, params).fetchall()]

    async def fetchrow(self, sql, *params, timeout=None):
        row = self._run(sql, params).fetchone()
        return dict(row) if row else None

    async def fetchval(self, sql, *params, timeout=None):
        row = self._run(sql, params).fetchone()
        return row[0] if row else None


def _make_session(db: sqlite3.Connection) -> Session:
    session = Session.__new__(Session)
    session._conn = _SqliteConnection(db)
    session._echo = False
    session._tx = None
    session._locker = asyncio.Lock()

    async def _noop_ensure_connection(lock: bool = True):
        return None

    session._ensure_connection = _noop_ensure_connection
    return session


@pytest.fixture
def db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("ATTACH DATABASE ':memory:' AS org")
    conn.execute("ATTACH DATABASE ':memory:' AS public")
    conn.executescript(_SCHEMA)
    conn.executemany(
        "INSERT INTO public.system_locale (id, is_default) VALUES (?, ?)",
        [(str(DEFAULT_LOCALE_ID), 1), (str(REPORTED_LOCALE_ID), 0), (str(OTHER_LOCALE_ID), 0)],
    )
    yield conn
    conn.close()


def _add_ministry(
    db: sqlite3.Connection,
    translations: dict[UUID, str],
    *,
    ministry_id: UUID | None = None,
    sequence: float = 1,
    status: str = MinistryStatus.ACTIVE.value,
    is_deleted: bool = False,
    member_role: str | None = MinistryMemberRole.PRIMARY.value,
) -> UUID:
    ministry_id = ministry_id or uuid4()
    db.execute("INSERT INTO org.ministry (id, status, is_deleted, sequence) VALUES (?, ?, ?, ?)", (str(ministry_id), status, int(is_deleted), sequence))
    for locale_id, name in translations.items():
        db.execute(
            "INSERT INTO org.ministry_translation (id, ministry_id, locale_id, name) VALUES (?, ?, ?, ?)",
            (str(uuid4()), str(ministry_id), str(locale_id), name),
        )
    if member_role:
        db.execute(
            "INSERT INTO org.ministry_member (id, ministry_id, user_id, member_role) VALUES (?, ?, ?, ?)",
            (str(uuid4()), str(ministry_id), str(USER_ID), member_role),
        )
    return ministry_id


async def _owned_names(db: sqlite3.Connection, locale_id: UUID | None) -> dict[UUID, str | None]:
    items = await MinistryRepository(_make_session(db)).list_owned_active(USER_ID, locale_id)
    return {item.id: item.name for item in items}


@pytest.mark.asyncio
async def test_list_owned_active_prefers_requested_locale_over_default_and_other(db):
    ministry_id = _add_ministry(db, {REPORTED_LOCALE_ID: "Requested", DEFAULT_LOCALE_ID: "Default", OTHER_LOCALE_ID: "Other"})

    assert (await _owned_names(db, REPORTED_LOCALE_ID))[ministry_id] == "Requested"


@pytest.mark.asyncio
async def test_list_owned_active_falls_back_to_default_when_requested_missing(db):
    ministry_id = _add_ministry(db, {DEFAULT_LOCALE_ID: "Default", OTHER_LOCALE_ID: "Other"})

    assert (await _owned_names(db, REPORTED_LOCALE_ID))[ministry_id] == "Default"


@pytest.mark.asyncio
async def test_list_owned_active_falls_back_to_available_when_requested_and_default_missing(db):
    ministry_id = _add_ministry(db, {OTHER_LOCALE_ID: "Other"})

    assert (await _owned_names(db, REPORTED_LOCALE_ID))[ministry_id] == "Other"


@pytest.mark.asyncio
async def test_list_owned_active_without_locale_falls_back_to_default_then_available(db):
    with_default = _add_ministry(db, {DEFAULT_LOCALE_ID: "Default", OTHER_LOCALE_ID: "Other"}, sequence=1)
    without_default = _add_ministry(db, {OTHER_LOCALE_ID: "Other"}, sequence=2)

    names = await _owned_names(db, None)

    assert names[with_default] == "Default"
    assert names[without_default] == "Other"


@pytest.mark.asyncio
async def test_list_owned_active_reported_softball_keeps_name_through_api_mapping(db):
    _add_ministry(db, {REPORTED_LOCALE_ID: "Softball"}, ministry_id=REPORTED_MINISTRY_ID)
    repository = MinistryRepository(_make_session(db))

    for locale_id in (REPORTED_LOCALE_ID, OTHER_LOCALE_ID, None):
        items = await repository.list_owned_active(USER_ID, locale_id)
        api = ministry_list_to_api(MinistryListResult(items=items))
        assert [(item.id, item.name) for item in api.items] == [(REPORTED_MINISTRY_ID, "Softball")]


@pytest.mark.asyncio
async def test_list_owned_active_without_translations_has_null_name(db):
    ministry_id = _add_ministry(db, {})

    assert (await _owned_names(db, REPORTED_LOCALE_ID)) == {ministry_id: None}
    assert (await _owned_names(db, None)) == {ministry_id: None}


@pytest.mark.asyncio
async def test_list_owned_active_keeps_membership_status_deletion_and_ordering(db):
    second = _add_ministry(db, {OTHER_LOCALE_ID: "Second"}, sequence=2)
    first = _add_ministry(db, {OTHER_LOCALE_ID: "First"}, sequence=1)
    pending = _add_ministry(db, {OTHER_LOCALE_ID: "Pending"}, sequence=3, status=MinistryStatus.PENDING_APPROVAL.value)
    _add_ministry(db, {OTHER_LOCALE_ID: "Deleted"}, sequence=4, is_deleted=True)
    _add_ministry(db, {OTHER_LOCALE_ID: "Not mine"}, sequence=5, member_role=None)
    repository = MinistryRepository(_make_session(db))

    active = await repository.list_owned_active(USER_ID, REPORTED_LOCALE_ID)
    with_pending = await repository.list_owned_active(USER_ID, REPORTED_LOCALE_ID, include_pending=True)

    assert [(item.id, item.name) for item in active] == [(first, "First"), (second, "Second")]
    assert [item.id for item in with_pending] == [first, second, pending]


@pytest.mark.asyncio
async def test_list_active_falls_back_and_keeps_ordering(db):
    second = _add_ministry(db, {OTHER_LOCALE_ID: "Other"}, sequence=2, member_role=None)
    first = _add_ministry(db, {DEFAULT_LOCALE_ID: "Default"}, sequence=1, member_role=None)
    repository = MinistryRepository(_make_session(db))

    for locale_id in (REPORTED_LOCALE_ID, None):
        items = await repository.list_active(locale_id)
        assert [(item.id, item.name) for item in items] == [(first, "Default"), (second, "Other")]


@pytest.mark.asyncio
async def test_fetch_steward_directory_falls_back_and_keeps_pagination(db):
    first = _add_ministry(db, {REPORTED_LOCALE_ID: "Requested", DEFAULT_LOCALE_ID: "Default"}, sequence=1)
    second = _add_ministry(db, {OTHER_LOCALE_ID: "Other"}, sequence=2)
    _add_ministry(db, {OTHER_LOCALE_ID: "Third"}, sequence=3)
    repository = MinistryRepository(_make_session(db))

    items, count = await repository.fetch_steward_directory(StewardDirectoryQueryCommand(page=0, page_size=2), REPORTED_LOCALE_ID)
    no_locale_items, _ = await repository.fetch_steward_directory(StewardDirectoryQueryCommand(page=0, page_size=2), None)

    assert count == 3
    assert [(item.id, item.name) for item in items] == [(first, "Requested"), (second, "Other")]
    assert [(item.id, item.name) for item in no_locale_items] == [(first, "Default"), (second, "Other")]
