"""
Run basedpyright against the distributed_trace typing fixtures.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

TYPING_DIR = Path(__file__).resolve().parent
REPO_ROOT = TYPING_DIR.parents[1]
OK_FILE = TYPING_DIR / "distributed_trace_ok.py"
FAIL_FILE = TYPING_DIR / "distributed_trace_fail.py"


def _run_basedpyright(target: Path) -> subprocess.CompletedProcess[str]:
    if shutil.which("uv"):
        command = ["uv", "run", "--with", "basedpyright", "basedpyright", "--level", "error", str(target)]
    else:
        command = ["basedpyright", "--level", "error", str(target)]
    return subprocess.run(command, capture_output=True, text=True, cwd=REPO_ROOT, check=False)


@pytest.fixture(scope="module")
def basedpyright_available() -> None:
    probe = _run_basedpyright(OK_FILE)
    if probe.returncode not in {0, 1}:
        pytest.skip(f"basedpyright unavailable: {probe.stderr or probe.stdout}")


def test_accepted_distributed_trace_shapes_type_check(basedpyright_available) -> None:
    result = _run_basedpyright(OK_FILE)
    assert result.returncode == 0, result.stdout + result.stderr


def test_rejected_distributed_trace_shapes_fail_type_check(basedpyright_available) -> None:
    result = _run_basedpyright(FAIL_FILE)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "ordinary_sync" in output or "Argument of type" in output
    assert "set_attribute" in output or "dict" in output or "list" in output
