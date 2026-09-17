"""
Tests for Mock account/Ministry CSV schema, filenames, and local retention.
"""

from datetime import datetime
from pathlib import Path

import pytest

from portal.application.cli.mock_account_archive import (
    ACCOUNT_CSV_COLUMNS,
    MINISTRY_CSV_COLUMNS,
    MockSeedArchiveCollisionError,
    compute_archive_filenames,
    remove_previous_archive_pair,
    write_csv,
)


def test_compute_archive_filenames_matches_exact_schema():
    moment = datetime(2026, 9, 17, 14, 5)

    filenames = compute_archive_filenames(moment, "dev")

    assert filenames.account_filename == "2026-09-17_1405_dev_test_account.csv"
    assert filenames.ministry_filename == "2026-09-17_1405_dev_ministry.csv"


def test_write_csv_writes_header_and_rows(tmp_path: Path):
    path = tmp_path / "account.csv"
    rows = [
        {
            "email": "personal.aaaa@test.local",
            "first_name": "Personal+aaaa",
            "last_name": "Mock",
            "persona": "personal",
            "purpose": "x",
            "is_active": True,
            "created_in_run": True,
        }
    ]

    write_csv(path, ACCOUNT_CSV_COLUMNS, rows)

    content = path.read_text(encoding="utf-8").splitlines()
    assert content[0] == ",".join(ACCOUNT_CSV_COLUMNS)
    assert content[1] == "personal.aaaa@test.local,Personal+aaaa,Mock,personal,x,true,true"


def test_write_csv_never_overwrites_existing_file(tmp_path: Path):
    path = tmp_path / "account.csv"
    path.write_text("existing", encoding="utf-8")

    with pytest.raises(MockSeedArchiveCollisionError):
        write_csv(path, ACCOUNT_CSV_COLUMNS, [])

    assert path.read_text(encoding="utf-8") == "existing"


def test_ministry_csv_columns_match_schema():
    assert MINISTRY_CSV_COLUMNS == (
        "ministry_code",
        "ministry_name",
        "status",
        "primary_steward_email",
        "secondary_steward_emails",
        "purpose",
        "created_in_run",
    )


def test_remove_previous_archive_pair_deletes_only_same_env_older_pair(tmp_path: Path):
    keep_account = tmp_path / "2026-09-17_1405_dev_test_account.csv"
    keep_ministry = tmp_path / "2026-09-17_1405_dev_ministry.csv"
    old_account = tmp_path / "2026-09-17_1300_dev_test_account.csv"
    old_ministry = tmp_path / "2026-09-17_1300_dev_ministry.csv"
    other_env_account = tmp_path / "2026-09-17_1300_stg_test_account.csv"
    for path in (keep_account, keep_ministry, old_account, old_ministry, other_env_account):
        path.write_text("x", encoding="utf-8")

    remove_previous_archive_pair(tmp_path, env="dev", keep=(keep_account, keep_ministry))

    assert keep_account.exists()
    assert keep_ministry.exists()
    assert not old_account.exists()
    assert not old_ministry.exists()
    assert other_env_account.exists()


def test_remove_previous_archive_pair_is_a_noop_when_output_dir_missing(tmp_path: Path):
    missing_dir = tmp_path / "does-not-exist"

    remove_previous_archive_pair(missing_dir, env="dev", keep=(missing_dir / "a.csv", missing_dir / "b.csv"))
