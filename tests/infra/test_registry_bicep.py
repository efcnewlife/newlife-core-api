"""
Offline policy checks for the shared registry Bicep (EFC-294, region moved by EFC-306).

Compiles infra/azure/registry with the local Bicep CLI and checks that the registry is pinned to Canada Central,
so it does not follow the location of an existing resource group created in Canada East.
Never signs in to Azure; a passing run does not prove Azure accepts the template.

    uv run pytest tests/infra/test_registry_bicep.py -v
"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
REGISTRY_DIR = ROOT / "infra" / "azure" / "registry"


def _bicep() -> str | None:
    configured = os.getenv("BICEP")
    if configured:
        return shutil.which(configured)
    fallback = Path.home() / ".azure" / "bin" / "bicep"
    return shutil.which("bicep") or (str(fallback) if fallback.exists() else None)


BICEP = _bicep()
pytestmark = pytest.mark.skipif(BICEP is None, reason="bicep not found; install it with: az bicep install")


@pytest.fixture(scope="module")
def parameters() -> dict[str, Any]:
    result = subprocess.run([BICEP, "build-params", str(REGISTRY_DIR / "main.bicepparam"), "--stdout"], capture_output=True, text=True, check=True)
    params = json.loads(json.loads(result.stdout)["parametersJson"])["parameters"]
    return {name: entry.get("value") for name, entry in params.items()}


def test_registry_is_pinned_to_canada_central(parameters: dict[str, Any]) -> None:
    assert parameters["location"] == "canadacentral"


def test_registry_keeps_its_name(parameters: dict[str, Any]) -> None:
    assert parameters["registryName"] == "efcnewlifecr"
