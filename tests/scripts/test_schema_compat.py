"""
Offline tests for scripts/schema_compat.py: a target version's Alembic history against a database revision.
No database is involved; the revision is what the operator read from alembic_version.
"""

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "schema_compat.py"

_spec = importlib.util.spec_from_file_location("schema_compat", SCRIPT)
schema_compat = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(schema_compat)


def _revision(versions: Path, rev: str, down: str | None) -> None:
    down_repr = repr(down)
    versions.joinpath(f"{rev}.py").write_text(f"revision = {rev!r}\ndown_revision = {down_repr}\n")


@pytest.fixture
def script_dir(tmp_path: Path) -> ScriptDirectory:
    """History a <- b <- c, as an older checkout would have it."""
    versions = tmp_path / "versions"
    versions.mkdir()
    _revision(versions, "a", None)
    _revision(versions, "b", "a")
    _revision(versions, "c", "b")
    return ScriptDirectory(str(tmp_path))


def test_database_at_head_is_current(script_dir):
    assert schema_compat.decide(script_dir, "c") == schema_compat.Decision.CURRENT


def test_database_behind_head_needs_migration(script_dir):
    assert schema_compat.decide(script_dir, "a") == schema_compat.Decision.BEHIND


def test_empty_database_needs_migration(script_dir):
    assert schema_compat.decide(script_dir, None) == schema_compat.Decision.BEHIND


def test_revision_unknown_to_this_version_is_ahead(script_dir):
    # The database was migrated by a newer version: this older image was not written for that schema.
    assert schema_compat.decide(script_dir, "d") == schema_compat.Decision.AHEAD


def test_multiple_heads_are_refused(script_dir):
    _revision(Path(script_dir.versions), "x", "a")
    with pytest.raises(schema_compat.SchemaCompatError, match="heads"):
        schema_compat.decide(ScriptDirectory(script_dir.dir), "c")


def test_cli_exit_codes_and_messages():
    head = ScriptDirectory(str(ROOT / "alembic")).get_current_head()

    def run(*args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, capture_output=True, text=True, check=False)

    current = run(head)
    assert current.returncode == 0, current.stderr
    assert "current" in current.stdout

    behind = run("none")
    assert behind.returncode == 3
    assert "behind" in behind.stdout

    ahead = run("ffffffffffff")
    assert ahead.returncode == 4
    assert "ahead" in ahead.stdout

    usage = run()
    assert usage.returncode == 2


def test_cli_reads_another_checkout(script_dir, tmp_path):
    checkout = tmp_path / "older-checkout"
    shutil.copytree(script_dir.versions, checkout / "alembic" / "versions")
    result = subprocess.run([sys.executable, str(SCRIPT), "b", str(checkout)], capture_output=True, text=True, check=False)
    assert result.returncode == 3, result.stderr
    assert "expects c" in result.stdout

    missing = subprocess.run([sys.executable, str(SCRIPT), "b", str(tmp_path / "nowhere")], capture_output=True, text=True, check=False)
    assert missing.returncode == 1
