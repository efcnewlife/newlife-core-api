"""
Tests for the SharePoint archive-writer facade (folder routing + collision refusal).
"""

from pathlib import Path

import pytest

from portal.providers.sharepoint_archive_provider import SharePointArchiveProvider


class FakeSharePoint:
    def __init__(self, *, configured: bool = True, existing_paths: set[str] | None = None):
        self._configured = configured
        self._existing_paths = existing_paths or set()
        self.uploaded: dict[str, bytes] = {}

    def is_configured(self) -> bool:
        return self._configured

    async def item_exists(self, *, drive_id: str, item_path: str) -> bool:
        return item_path in self._existing_paths

    async def upload_bytes(self, *, drive_id: str, item_path: str, content: bytes) -> None:
        self.uploaded[item_path] = content


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.asyncio
async def test_upload_csv_pair_routes_dev_and_stg_to_distinct_folders(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from portal.config import settings

    monkeypatch.setattr(settings, "SHAREPOINT_TEST_ACCOUNT_FOLDER_DEV", "Test Account/dev")
    monkeypatch.setattr(settings, "SHAREPOINT_TEST_ACCOUNT_FOLDER_STG", "Test Account/stg")
    monkeypatch.setattr(settings, "SHAREPOINT_DRIVE_ID", "drive-1")

    fake = FakeSharePoint()
    provider = SharePointArchiveProvider(sharepoint_factory=lambda: fake)
    account_csv = _write(tmp_path / "a.csv", "account")
    ministry_csv = _write(tmp_path / "m.csv", "ministry")

    await provider.upload_csv_pair(env="dev", account_csv=account_csv, ministry_csv=ministry_csv)

    assert set(fake.uploaded) == {"Test Account/dev/a.csv", "Test Account/dev/m.csv"}


@pytest.mark.asyncio
async def test_upload_csv_pair_refuses_to_overwrite_an_existing_remote_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from portal.config import settings

    monkeypatch.setattr(settings, "SHAREPOINT_TEST_ACCOUNT_FOLDER_DEV", "Test Account/dev")
    monkeypatch.setattr(settings, "SHAREPOINT_DRIVE_ID", "drive-1")

    fake = FakeSharePoint(existing_paths={"Test Account/dev/a.csv"})
    provider = SharePointArchiveProvider(sharepoint_factory=lambda: fake)
    account_csv = _write(tmp_path / "a.csv", "account")
    ministry_csv = _write(tmp_path / "m.csv", "ministry")

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        await provider.upload_csv_pair(env="dev", account_csv=account_csv, ministry_csv=ministry_csv)

    assert fake.uploaded == {}


@pytest.mark.asyncio
async def test_upload_csv_pair_raises_when_not_configured(tmp_path: Path):
    fake = FakeSharePoint(configured=False)
    provider = SharePointArchiveProvider(sharepoint_factory=lambda: fake)
    account_csv = _write(tmp_path / "a.csv", "account")
    ministry_csv = _write(tmp_path / "m.csv", "ministry")

    with pytest.raises(RuntimeError, match="not configured"):
        await provider.upload_csv_pair(env="dev", account_csv=account_csv, ministry_csv=ministry_csv)


@pytest.mark.asyncio
async def test_upload_csv_pair_rejects_unmapped_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from portal.config import settings

    monkeypatch.setattr(settings, "SHAREPOINT_DRIVE_ID", "drive-1")
    fake = FakeSharePoint()
    provider = SharePointArchiveProvider(sharepoint_factory=lambda: fake)
    account_csv = _write(tmp_path / "a.csv", "account")
    ministry_csv = _write(tmp_path / "m.csv", "ministry")

    with pytest.raises(ValueError, match="prod"):
        await provider.upload_csv_pair(env="prod", account_csv=account_csv, ministry_csv=ministry_csv)
