"""
Tests for VerbService.
"""
from uuid import uuid4

import pytest

from portal.application.rbac.results import VerbListResult
from portal.application.rbac.verb_service import VerbService
from portal.domain.rbac.entities import VerbListItem


class StubVerbRepository:
    def __init__(self, items: list[VerbListItem] | None = None):
        self._items = items or []
        self.called_with = None

    async def list_active_by_locale(self, locale_id):
        self.called_with = locale_id
        return self._items


class StubVerbListCache:
    def __init__(self, cached: list[VerbListItem] | None = None):
        self._cached = cached
        self.set_calls: list = []

    async def get(self, locale_id):
        return self._cached

    async def set(self, locale_id, items):
        self.set_calls.append((locale_id, items))


@pytest.mark.asyncio
async def test_get_verb_list_returns_empty_without_locale_context(monkeypatch):
    monkeypatch.setattr(
        "portal.application.rbac.verb_service.get_request_context",
        lambda: None,
    )
    service = VerbService(StubVerbRepository(), StubVerbListCache())
    result = await service.get_verb_list()
    assert result == VerbListResult(items=[])


@pytest.mark.asyncio
async def test_get_verb_list_uses_cache(monkeypatch):
    locale_id = uuid4()
    cached_item = VerbListItem(
        id=uuid4(),
        action="read",
        name="Read",
        description=None,
    )

    class ReqCtx:
        resolved_locale_id = locale_id

    monkeypatch.setattr(
        "portal.application.rbac.verb_service.get_request_context",
        lambda: ReqCtx(),
    )
    repo = StubVerbRepository([cached_item])
    cache = StubVerbListCache([cached_item])
    service = VerbService(repo, cache)
    result = await service.get_verb_list()
    assert len(result.items) == 1
    assert result.items[0].action == "read"
    assert repo.called_with is None


@pytest.mark.asyncio
async def test_get_verb_list_loads_from_repository_and_caches(monkeypatch):
    locale_id = uuid4()
    item = VerbListItem(
        id=uuid4(),
        action="create",
        name="Create",
        description="Create resource",
    )

    class ReqCtx:
        resolved_locale_id = locale_id

    monkeypatch.setattr(
        "portal.application.rbac.verb_service.get_request_context",
        lambda: ReqCtx(),
    )
    repo = StubVerbRepository([item])
    cache = StubVerbListCache(None)
    service = VerbService(repo, cache)
    result = await service.get_verb_list()
    assert len(result.items) == 1
    assert repo.called_with == locale_id
    assert len(cache.set_calls) == 1
