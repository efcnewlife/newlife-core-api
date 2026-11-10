"""
Run basedpyright against the capture_exception typing fixtures.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

TYPING_DIR = Path(__file__).resolve().parent
REPO_ROOT = TYPING_DIR.parents[1]
OK_FILE = TYPING_DIR / "capture_exception_ok.py"
FAIL_FILE = TYPING_DIR / "capture_exception_fail.py"


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


def test_accepted_capture_exception_shapes_type_check(basedpyright_available) -> None:
    result = _run_basedpyright(OK_FILE)
    assert result.returncode == 0, result.stdout + result.stderr


def test_rejected_capture_exception_shapes_fail_type_check(basedpyright_available) -> None:
    result = _run_basedpyright(FAIL_FILE)
    output = result.stdout + result.stderr
    assert result.returncode != 0, output
    assert "capture_exception" in output or "Argument of type" in output or "Too many arguments" in output
