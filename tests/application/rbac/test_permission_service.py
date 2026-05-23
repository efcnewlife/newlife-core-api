"""
Tests for PermissionService.
"""
from uuid import uuid4

import pytest

from portal.application.audit.rbac_audit_service import RbacAuditService
from portal.application.rbac.permission_service import PermissionService
from portal.application.rbac.results import PermissionListResult
from portal.domain.rbac.entities import PermissionListItem, PermissionRecord


class StubPermissionRepository:
    def __init__(
        self,
        list_items=None,
        user_permissions=None,
        all_permissions=None,
    ):
        self._list_items = list_items or []
        self._user_permissions = user_permissions or []
        self._all_permissions = all_permissions or []
        self.list_for_locale_called = False
        self.list_user_role_called = False

    async def list_for_locale(self, locale_id):
        self.list_for_locale_called = True
        return self._list_items

    async def list_user_role_permissions(self, user_id):
        self.list_user_role_called = True
        return self._user_permissions

    async def list_all_permissions(self):
        return self._all_permissions


class StubPermissionCache:
    def __init__(self, cached_json: str | None = None):
        self._cached_json = cached_json
        self.set_calls: list = []
        self.cleared_user_ids: list = []
        self.init_calls: list = []

    async def get_permission_list_json(self, locale_id):
        return self._cached_json

    async def set_permission_list_json(self, locale_id, payload_json):
        self.set_calls.append((locale_id, payload_json))

    async def clear_user_permissions_cache(self, user_id):
        self.cleared_user_ids.append(user_id)

    async def init_user_permissions_cache(self, user_id, permissions, expire):
        await self.clear_user_permissions_cache(user_id)
        self.init_calls.append((user_id, permissions, expire))
        return [p.code for p in permissions]


class StubRbacAuditService:
    def create_log(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_get_permission_list_returns_empty_without_locale_context(monkeypatch):
    monkeypatch.setattr(
        "portal.application.rbac.permission_service.get_request_context",
        lambda: None,
    )
    service = PermissionService(
        StubPermissionRepository(),
        StubPermissionCache(),
        StubRbacAuditService(),
    )
    result = await service.get_permission_list()
    assert result == PermissionListResult(items=[])


@pytest.mark.asyncio
async def test_get_permission_list_uses_cache(monkeypatch):
    locale_id = uuid4()
    list_item = PermissionListItem(
        id=uuid4(),
        name="Read users",
        code="system.user.read",
        is_active=True,
        description=None,
        remark=None,
        resource_id=uuid4(),
        verb_id=uuid4(),
    )
    cached_list = PermissionListResult(items=[list_item])

    class ReqCtx:
        resolved_locale_id = locale_id

    monkeypatch.setattr(
        "portal.application.rbac.permission_service.get_request_context",
        lambda: ReqCtx(),
    )
    repo = StubPermissionRepository([list_item])
    cache = StubPermissionCache(cached_list.model_dump_json())
    service = PermissionService(repo, cache, StubRbacAuditService())
    result = await service.get_permission_list()
    assert len(result.items) == 1
    assert result.items[0].code == "system.user.read"
    assert repo.list_for_locale_called is False


@pytest.mark.asyncio
async def test_init_user_permissions_cache_superuser(monkeypatch):
    user_id = uuid4()
    perm = PermissionRecord(
        code="system.user.read",
        resource_code="system.user",
        action="read",
    )

    class User:
        id = user_id
        is_superuser = True

    repo = StubPermissionRepository(all_permissions=[perm])
    cache = StubPermissionCache()
    service = PermissionService(repo, cache, StubRbacAuditService())
    codes = await service.init_user_permissions_cache(user=User(), expire=3600)
    assert codes == ["system.user.read"]
    assert user_id in cache.cleared_user_ids
    assert len(cache.init_calls) == 1
    assert repo.list_user_role_called is False
