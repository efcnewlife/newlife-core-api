"""
Tests for the seed-mock-users orchestration service (fake session/archive-writer seam).
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import ACCOUNT_CSV_COLUMNS, MINISTRY_CSV_COLUMNS, MockSeedArchiveCollisionError, read_csv_rows
from portal.application.cli.seed_mock_users_service import (
    MockSeedArchiveUploadError,
    MockSeedCatalogPrerequisiteError,
    MockSnapshotExistsError,
    SeedMockUsersService,
)


class FakeSession:
    """Minimal fake standing in for portal.libs.database.Session."""

    def __init__(self, *, locale_rows=None, raise_on_insert: dict[str, Exception] | None = None, existing_users: list[dict] | None = None):
        self._locale_rows = [{"id": uuid4(), "language_code": "en"}] if locale_rows is None else locale_rows
        self._existing_users = existing_users or []
        self._raise_on_insert = raise_on_insert or {}
        self.inserted: dict[str, list[dict]] = defaultdict(list)
        self.committed = False
        self.rolled_back = False
        self._pending_select = ()
        self._pending_model = None
        self._pending_exc = None
        self._last_user_id = None

    def select(self, *args, **kwargs):
        self._pending_select = args
        return self

    def where(self, *args, **kwargs):
        return self

    def _selected_model_name(self) -> str | None:
        if not self._pending_select:
            return None
        first = self._pending_select[0]
        mapped = getattr(first, "class_", first)
        return getattr(mapped, "__name__", None)

    async def fetch(self):
        if self._selected_model_name() == "AuthUser":
            return self._existing_users
        return self._locale_rows

    async def fetchval(self):
        return None

    async def fetchrow(self):
        return {"id": self._last_user_id}

    def insert(self, model):
        self._pending_model = model
        return self

    def values(self, **kwargs):
        name = self._pending_model.__name__
        if name == "AuthUser":
            self._last_user_id = kwargs["id"]
        self._pending_exc = self._raise_on_insert.get(name)
        self.inserted[name].append(kwargs)
        return self

    async def execute(self):
        if self._pending_exc is not None:
            exc = self._pending_exc
            self._pending_exc = None
            raise exc
        return None

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeArchiveWriter:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.calls: list[tuple[Path, Path]] = []

    async def upload_csv_pair(self, *, account_csv: Path, ministry_csv: Path):
        self.calls.append((account_csv, ministry_csv))
        if self.fail:
            raise RuntimeError("simulated SharePoint upload failure")


def _token_factory():
    count = 0

    def next_token() -> str:
        nonlocal count
        token = f"{count:04x}"
        count += 1
        return token

    return next_token


def _service(tmp_path: Path, *, session=None, archive_writer=None, clock=None) -> SeedMockUsersService:
    return SeedMockUsersService(
        session or FakeSession(),
        archive_writer or FakeArchiveWriter(),
        env="dev",
        default_locale_code="en",
        output_dir=tmp_path,
        random_token=_token_factory(),
        clock=clock or (lambda: datetime(2026, 9, 17, 14, 5)),
    )


@pytest.mark.asyncio
async def test_seed_mock_users_creates_complete_account_and_ministry_inventory(tmp_path: Path):
    session = FakeSession()
    archive_writer = FakeArchiveWriter()

    result = await _service(tmp_path, session=session, archive_writer=archive_writer).run()

    user_emails = [row["email"] for row in session.inserted["AuthUser"]]
    personas = [email.split(".")[0] for email in user_emails]
    assert personas.count("personal") == 5
    assert personas.count("steward") == 3
    assert personas.count("owner") == 1
    assert personas.count("inactive") == 1
    assert all(email.endswith("@test.local") for email in user_emails)
    assert session.inserted["AuthUser"][-1]["is_active"] is False
    assert session.inserted["AuthUser"][-1]["verified"] is True

    assert len(session.inserted["OrgMinistry"]) == 10
    assert all(row["ministry_type_id"] is None for row in session.inserted["OrgMinistry"])
    assert all(row["status"] == "active" for row in session.inserted["OrgMinistry"])
    assert len(session.inserted["OrgMinistrySchedule"]) == 10

    names = [row["name"] for row in session.inserted["OrgMinistryTranslation"]]
    assert len(names) == 10
    assert all("dev-2026-09-17_1405" in name for name in names)
    for label in ("Alpha", "Badminton", "Basketball", "Chinese School", "Pickleball", "Softball", "Stretching", "Supporting SOSO Ministry", "Choir", "Prayer"):
        assert any(label in name for name in names)

    member_roles = [row["member_role"] for row in session.inserted["OrgMinistryMember"]]
    assert member_roles.count("primary") == 10
    assert member_roles.count("secondary") == 15

    assert session.committed is True
    assert archive_writer.calls == [(result.account_csv, result.ministry_csv)]

    account_rows = read_csv_rows(result.account_csv)
    ministry_rows = read_csv_rows(result.ministry_csv)
    assert list(account_rows[0].keys()) == list(ACCOUNT_CSV_COLUMNS)
    assert list(ministry_rows[0].keys()) == list(MINISTRY_CSV_COLUMNS)
    assert len(account_rows) == 10
    assert len(ministry_rows) == 10
    assert len({row["purpose"] for row in account_rows}) == 10
    assert [row["persona"] for row in account_rows].count("personal") == 5
    assert all("dev-2026-09-17_1405" in row["ministry_name"] for row in ministry_rows)
    assert all(row["status"] == "active" for row in ministry_rows)
    assert all(row["created_in_run"] == "true" for row in account_rows)
    assert all(row["created_in_run"] == "true" for row in ministry_rows)
    assert result.run_identity == "dev-2026-09-17_1405"


@pytest.mark.asyncio
async def test_seed_mock_users_fails_fast_when_default_locale_missing(tmp_path: Path):
    session = FakeSession(locale_rows=[])

    with pytest.raises(MockSeedCatalogPrerequisiteError, match="init-all"):
        await _service(tmp_path, session=session).run()

    assert session.inserted == {}
    assert session.committed is False


@pytest.mark.asyncio
async def test_seed_mock_users_reports_clear_error_when_ministry_type_is_not_nullable(tmp_path: Path):
    session = FakeSession(raise_on_insert={"OrgMinistry": NotNullViolationError("ministry_type_id")})

    with pytest.raises(RuntimeError, match="66fd53b703c7"):
        await _service(tmp_path, session=session).run()

    assert session.committed is False
    assert "OrgMinistryTranslation" not in session.inserted
    assert "OrgMinistryMember" not in session.inserted


@pytest.mark.asyncio
async def test_seed_mock_users_rejects_same_minute_archive_filename_collision(tmp_path: Path):
    session = FakeSession()
    (tmp_path / "2026-09-17_1405_dev_test_account.csv").write_text("existing", encoding="utf-8")
    archive_writer = FakeArchiveWriter()

    with pytest.raises(MockSeedArchiveCollisionError):
        await _service(tmp_path, session=session, archive_writer=archive_writer).run()

    assert session.committed is True
    assert archive_writer.calls == []


@pytest.mark.asyncio
async def test_seed_mock_users_archive_upload_failure_keeps_local_csv_and_reports_paths(tmp_path: Path):
    archive_writer = FakeArchiveWriter(fail=True)

    with pytest.raises(MockSeedArchiveUploadError) as exc_info:
        await _service(tmp_path, archive_writer=archive_writer).run()

    error = exc_info.value
    assert error.account_csv.exists()
    assert error.ministry_csv.exists()
    assert "simulated SharePoint upload failure" not in str(error)
    assert len(read_csv_rows(error.account_csv)) == 10
    assert len(read_csv_rows(error.ministry_csv)) == 10


@pytest.mark.asyncio
async def test_seed_mock_users_retains_only_latest_local_pair_for_env(tmp_path: Path):
    old_account = tmp_path / "2026-09-17_1300_dev_test_account.csv"
    old_ministry = tmp_path / "2026-09-17_1300_dev_ministry.csv"
    old_account.write_text("old", encoding="utf-8")
    old_ministry.write_text("old", encoding="utf-8")

    result = await _service(tmp_path).run()

    assert not old_account.exists()
    assert not old_ministry.exists()
    assert result.account_csv.exists()
    assert result.ministry_csv.exists()


@pytest.mark.asyncio
async def test_seed_mock_users_rejects_a_second_run_while_a_snapshot_exists(tmp_path: Path):
    session = FakeSession(existing_users=[{"id": uuid4(), "email": "personal.old1@test.local"}])
    archive_writer = FakeArchiveWriter()

    with pytest.raises(MockSnapshotExistsError, match="remove-mock-data"):
        await _service(tmp_path, session=session, archive_writer=archive_writer).run()

    assert session.inserted == {}
    assert session.committed is False
    assert archive_writer.calls == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_seed_mock_users_is_eligible_again_after_snapshot_cleanup(tmp_path: Path):
    session = FakeSession(existing_users=[])
    archive_writer = FakeArchiveWriter()

    result = await _service(tmp_path, session=session, archive_writer=archive_writer).run()

    assert len(session.inserted["AuthUser"]) == 10
    assert len(read_csv_rows(result.ministry_csv)) == 10
    assert archive_writer.calls == [(result.account_csv, result.ministry_csv)]
