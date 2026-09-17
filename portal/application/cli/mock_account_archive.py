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


@dataclass(frozen=True)
class ArchiveFilenames:
    account_filename: str
    ministry_filename: str


def compute_archive_filenames(moment: datetime, env: str) -> ArchiveFilenames:
    """Build the exact `YYYY-MM-DD_HHMM_<env>_*.csv` filename pair for one run."""
    stamp = moment.strftime("%Y-%m-%d_%H%M")
    return ArchiveFilenames(account_filename=f"{stamp}_{env}_{_ACCOUNT_SUFFIX}", ministry_filename=f"{stamp}_{env}_{_MINISTRY_SUFFIX}")


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


def remove_previous_archive_pair(output_dir: Path, *, env: str, keep: tuple[Path, Path]) -> None:
    """Delete every other local CSV pair for this environment, keeping only the pair just written."""
    if not output_dir.exists():
        return
    keep_names = {path.name for path in keep}
    for suffix in (_ACCOUNT_SUFFIX, _MINISTRY_SUFFIX):
        for candidate in output_dir.glob(f"*_{env}_{suffix}"):
            if candidate.name not in keep_names:
                candidate.unlink()
