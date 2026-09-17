"""
Tests for the seed-mock-users orchestration service (fake session/archive-writer seam).
"""

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import MockSeedArchiveCollisionError
from portal.application.cli.seed_mock_users_service import MockSeedArchiveUploadError, MockSeedCatalogPrerequisiteError, SeedMockUsersService


class FakeSession:
    """Minimal fake standing in for portal.libs.database.Session."""

    def __init__(self, *, locale_rows=None, raise_on_insert: dict[str, Exception] | None = None):
        self._locale_rows = [{"id": uuid4(), "language_code": "en"}] if locale_rows is None else locale_rows
        self._raise_on_insert = raise_on_insert or {}
        self.inserted: dict[str, list[dict]] = defaultdict(list)
        self.committed = False
        self.rolled_back = False
        self._pending_model = None
        self._pending_exc = None
        self._last_user_id = None

    def select(self, *args, **kwargs):
        return self

    def where(self, *args, **kwargs):
        return self

    async def fetch(self):
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
        self.calls: list[tuple[str, Path, Path]] = []

    async def upload_csv_pair(self, *, env: str, account_csv: Path, ministry_csv: Path):
        self.calls.append((env, account_csv, ministry_csv))
        if self.fail:
            raise RuntimeError("simulated SharePoint upload failure")


def _service(tmp_path: Path, *, session=None, archive_writer=None, clock=None) -> SeedMockUsersService:
    return SeedMockUsersService(
        session or FakeSession(),
        archive_writer or FakeArchiveWriter(),
        env="dev",
        default_locale_code="en",
        output_dir=tmp_path,
        random_token=iter(["aaaa", "bbbb", "cccc", "dddd", "code"]).__next__,
        clock=clock or (lambda: datetime(2026, 9, 17, 14, 5)),
    )


@pytest.mark.asyncio
async def test_seed_mock_users_creates_four_personas_and_a_steward_ministry(tmp_path: Path):
    session = FakeSession()
    archive_writer = FakeArchiveWriter()

    result = await _service(tmp_path, session=session, archive_writer=archive_writer).run()

    assert len(session.inserted["AuthUser"]) == 4
    personas = [row["email"].split(".")[0] for row in session.inserted["AuthUser"]]
    assert personas == ["personal", "steward", "owner", "inactive"]

    inactive_row = session.inserted["AuthUser"][3]
    assert inactive_row["is_active"] is False
    assert inactive_row["verified"] is True

    assert len(session.inserted["OrgMinistry"]) == 1
    assert session.inserted["OrgMinistry"][0]["ministry_type_id"] is None

    assert len(session.inserted["OrgMinistryMember"]) == 1
    assert session.inserted["OrgMinistryMember"][0]["member_role"] == "primary"

    assert session.committed is True
    assert archive_writer.calls == [("dev", result.account_csv, result.ministry_csv)]
    assert result.account_csv.exists()
    assert result.ministry_csv.exists()


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

    # The whole seed (4 personas + Ministry) is one transaction; the schema error
    # aborts it before the single commit, so nothing is left half-durable.
    assert session.committed is False
    assert "OrgMinistryTranslation" not in session.inserted
    assert "OrgMinistryMember" not in session.inserted


@pytest.mark.asyncio
async def test_seed_mock_users_rejects_same_minute_archive_filename_collision(tmp_path: Path):
    (tmp_path / "2026-09-17_1405_dev_test_account.csv").write_text("existing", encoding="utf-8")
    archive_writer = FakeArchiveWriter()

    with pytest.raises(MockSeedArchiveCollisionError):
        await _service(tmp_path, archive_writer=archive_writer).run()

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
