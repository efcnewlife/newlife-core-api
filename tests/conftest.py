"""
Pytest: ensure project root is on sys.path when running from repo root.
"""

import os
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

# Set before portal.config loads .env (load_dotenv never overrides): tests must not reach real Sentry ingestion.
os.environ["SENTRY_ENABLED"] = "false"
os.environ["SENTRY_DSN"] = ""
os.environ["TELEMETRY_BACKEND"] = ""
# Same for a developer's Redis: this host never resolves (reserved TLD), so a test that reaches Redis fails.
# The opt-in Redis integration suite brings its own REDIS_URL.
if os.environ.get("PORTAL_REDIS_INTEGRATION") != "1":
    os.environ["REDIS_URL"] = "redis://redis.invalid:6379/0"

import pytest

from portal.container import Container


@pytest.fixture
def container() -> Container:
    """Root DI container for tests."""
    return Container()
