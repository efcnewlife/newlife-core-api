"""
Run the assembled application without Redis or a database, as unit tests have neither.
"""

import pytest

from portal.application.locale.locale_service import LocaleService
from portal.libs.utils import lifespan


async def _stub_get_locale_snapshot(_self):
    return {
        "active_locales": ["en-US"],
        "default_locale": "en-US",
        "normalized_map": {"en-us": "en-US"},
        "normalized_id_map": {},
        "language_buckets": {"en": ["en-US"]},
    }


async def _no_rate_limiters(_redis):
    return None


@pytest.fixture
def offline_app(monkeypatch):
    """Resolve request locales from a fixed snapshot and start without rate limiters: both would call Redis."""
    monkeypatch.setattr(LocaleService, "get_locale_snapshot", _stub_get_locale_snapshot)
    monkeypatch.setattr(lifespan, "create_redis_rate_limiters", _no_rate_limiters)
