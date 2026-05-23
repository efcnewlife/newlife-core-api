"""
Tests for LocaleService.
"""
from uuid import uuid4

import pytest

from portal.application.locale.locale_service import LocaleService
from portal.application.locale.mappers import locale_list_result_to_api
from portal.application.locale.results import LocaleSnapshotResult
from portal.domain.locale.entities import Locale


class StubLocaleRepository:
    def __init__(self, locales: list[Locale] | None = None):
        self._locales = locales or []

    async def list_all(self) -> list[Locale]:
        return self._locales


class StubLocaleCache:
    def __init__(self, snapshot: LocaleSnapshotResult | None = None):
        self._snapshot = snapshot
        self.populate_calls: list[LocaleSnapshotResult] = []
        self.clear_calls = 0

    async def get_snapshot(self) -> LocaleSnapshotResult | None:
        return self._snapshot

    async def populate(self, snapshot: LocaleSnapshotResult) -> None:
        self.populate_calls.append(snapshot)

    async def clear(self) -> None:
        self.clear_calls += 1


def _active_locale(
    *,
    language_code: str = "en",
    region_code: str | None = "US",
    is_default: bool = False,
) -> Locale:
    return Locale(
        id=uuid4(),
        language_code=language_code,
        script_code=None,
        region_code=region_code,
        name="English",
        native_name="English",
        is_active=True,
        is_default=is_default,
    )


@pytest.mark.asyncio
async def test_get_locale_snapshot_uses_cache_hit():
    cached = LocaleSnapshotResult(
        active_locales=["en-US"],
        default_locale="en-US",
        normalized_map={"en-us": "en-US"},
        normalized_id_map={"en-us": str(uuid4())},
        language_buckets={"en": ["en-US"]},
    )
    repo = StubLocaleRepository([_active_locale()])
    cache = StubLocaleCache(snapshot=cached)
    service = LocaleService(repo, cache)
    result = await service.get_locale_snapshot()
    assert result["active_locales"] == ["en-US"]
    assert result["default_locale"] == "en-US"
    assert len(cache.populate_calls) == 0


@pytest.mark.asyncio
async def test_get_locale_snapshot_populates_cache_on_miss():
    locale = _active_locale(is_default=True)
    repo = StubLocaleRepository([locale])
    cache = StubLocaleCache(snapshot=None)
    service = LocaleService(repo, cache)
    result = await service.get_locale_snapshot()
    assert result["default_locale"] == "en-US"
    assert "en-US" in result["active_locales"]
    assert len(cache.populate_calls) == 1
    assert cache.clear_calls == 0


@pytest.mark.asyncio
async def test_get_locale_codes_by_language():
    locale_id = uuid4()
    cached = LocaleSnapshotResult(
        active_locales=["zh-TW", "zh-CN"],
        default_locale="zh-TW",
        normalized_map={
            "zh-tw": "zh-TW",
            "zh-cn": "zh-CN",
        },
        normalized_id_map={
            "zh-tw": str(locale_id),
            "zh-cn": str(uuid4()),
        },
        language_buckets={"zh": ["zh-TW", "zh-CN"]},
    )
    service = LocaleService(StubLocaleRepository(), StubLocaleCache(snapshot=cached))
    codes = await service.get_locale_codes_by_language("zh")
    assert codes == ["zh-TW", "zh-CN"]


@pytest.mark.asyncio
async def test_get_locale_list_maps_to_api_schema():
    locale = _active_locale()
    service = LocaleService(StubLocaleRepository([locale]), StubLocaleCache())
    result = await service.get_locale_list_result()
    api = locale_list_result_to_api(result)
    assert len(api.items) == 1
    assert api.items[0].language_code == "en"
    assert api.items[0].region_code == "US"
