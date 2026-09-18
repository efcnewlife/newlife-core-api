"""
Account/Ministry inventory CSV schema, filenames, and local retention for
`seed-mock-users` (ADR 0025).
"""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ACCOUNT_CSV_COLUMNS = ("email", "first_name", "last_name", "persona", "purpose", "is_active", "created_in_run")
MINISTRY_CSV_COLUMNS = ("ministry_code", "ministry_name", "status", "primary_steward_email", "secondary_steward_emails", "purpose", "created_in_run")

_ACCOUNT_SUFFIX = "test_account.csv"
_MINISTRY_SUFFIX = "ministry.csv"


class MockSeedArchiveCollisionError(Exception):
    """Raised when the computed archive filename already exists (same-minute collision)."""


class MockSeedInventoryError(Exception):
    """Raised when the local account/Ministry CSV inventory pair is missing or ambiguous."""


@dataclass(frozen=True)
class ArchiveFilenames:
    account_filename: str
    ministry_filename: str


def compute_archive_filenames(moment: datetime, env: str) -> ArchiveFilenames:
    """Build the exact `YYYY-MM-DD_HHMM_<env>_*.csv` filename pair for one run."""
    stamp = moment.strftime("%Y-%m-%d_%H%M")
    return ArchiveFilenames(account_filename=f"{stamp}_{env}_{_ACCOUNT_SUFFIX}", ministry_filename=f"{stamp}_{env}_{_MINISTRY_SUFFIX}")


def compute_mock_run_identity(moment: datetime, env: str) -> str:
    """Return the shared `<env>-<YYYY-MM-DD_HHMM>` Mock run identity for one generation run."""
    return f"{env}-{moment.strftime('%Y-%m-%d_%H%M')}"


def parse_mock_run_identity(account_csv: Path, *, env: str) -> str:
    """Read the shared Mock run identity from the current account CSV filename."""
    suffix = f"_{env}_{_ACCOUNT_SUFFIX}"
    name = account_csv.name
    if not name.endswith(suffix):
        raise MockSeedInventoryError(f"Cannot read Mock run identity from {name}.")
    stamp = name[: -len(suffix)]
    if not stamp:
        raise MockSeedInventoryError(f"Cannot read Mock run identity from {name}.")
    return f"{env}-{stamp}"


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return "" if value is None else str(value)


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    """Write rows as CSV with an exact column order; never overwrite an existing file."""
    if path.exists():
        raise MockSeedArchiveCollisionError(f"Archive file already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_format_value(row.get(column)) for column in columns])


def find_local_archive_pair(output_dir: Path, *, env: str) -> tuple[Path, Path]:
    """
    Return the single local (account_csv, ministry_csv) pair for `env`.

    `seed-mock-users` retains only the latest local pair per env (`remove_previous_archive_pair`),
    so a consumer reading "the current Mock user inventory" must find exactly one pair. Raises
    MockSeedInventoryError when none exists or more than one candidate is present (ambiguous).
    """
    if not output_dir.exists():
        raise MockSeedInventoryError(f"No local Mock inventory found in {output_dir} for env {env!r}. Run seed-mock-users first.")

    account_matches = sorted(output_dir.glob(f"*_{env}_{_ACCOUNT_SUFFIX}"))
    ministry_matches = sorted(output_dir.glob(f"*_{env}_{_MINISTRY_SUFFIX}"))

    if not account_matches or not ministry_matches:
        raise MockSeedInventoryError(f"No local Mock inventory CSV pair found for env {env!r} in {output_dir}. Run seed-mock-users first.")
    if len(account_matches) > 1 or len(ministry_matches) > 1:
        raise MockSeedInventoryError(f"Ambiguous local Mock inventory for env {env!r}: expected exactly one CSV pair in {output_dir}.")

    account_csv, ministry_csv = account_matches[0], ministry_matches[0]
    account_stamp = account_csv.name[: -len(f"_{env}_{_ACCOUNT_SUFFIX}")]
    ministry_stamp = ministry_csv.name[: -len(f"_{env}_{_MINISTRY_SUFFIX}")]
    if account_stamp != ministry_stamp:
        raise MockSeedInventoryError(f"Mismatched local Mock inventory pair for env {env!r}: {account_csv.name} vs {ministry_csv.name}.")
    return account_csv, ministry_csv


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read a Mock inventory CSV into row dicts, keyed by header column."""
    with path.open("r", newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def remove_previous_archive_pair(output_dir: Path, *, env: str, keep: tuple[Path, Path]) -> None:
    """Delete every other local CSV pair for this environment, keeping only the pair just written."""
    if not output_dir.exists():
        return
    keep_names = {path.name for path in keep}
    for suffix in (_ACCOUNT_SUFFIX, _MINISTRY_SUFFIX):
        for candidate in output_dir.glob(f"*_{env}_{suffix}"):
            if candidate.name not in keep_names:
                candidate.unlink()
