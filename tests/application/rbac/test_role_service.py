"""
Tests for RoleService.
"""
from uuid import uuid4

import pytest

from portal.application.auth.results import UserSensitive
from portal.application.rbac.role_service import RoleService
from portal.domain.rbac.entities import RoleListItem


class StubRoleRepository:
    def __init__(
        self,
        active_roles=None,
        user_role_codes=None,
    ):
        self._active_roles = active_roles or []
        self._user_role_codes = user_role_codes or []
        self.list_active_called = False
        self.list_user_role_codes_called = False

    async def list_active_roles(self, locale_id):
        self.list_active_called = True
        return self._active_roles

    async def list_user_role_codes(self, user_id):
        self.list_user_role_codes_called = True
        return self._user_role_codes


class StubRoleCache:
    def __init__(self):
        self.cleared_user_ids: list = []
        self.init_calls: list = []

    async def clear_user_roles_cache(self, user_id):
        self.cleared_user_ids.append(user_id)

    async def init_user_roles_cache(self, user_id, role_codes, expire):
        await self.clear_user_roles_cache(user_id)
        self.init_calls.append((user_id, role_codes, expire))
        return role_codes


class StubRbacAuditService:
    def create_log(self, *args, **kwargs):
        pass


@pytest.mark.asyncio
async def test_get_active_roles_returns_empty_without_locale_context(monkeypatch):
    monkeypatch.setattr(
        "portal.application.rbac.role_service.get_request_context",
        lambda: None,
    )
    service = RoleService(
        StubRoleRepository(),
        StubRoleCache(),
        StubRbacAuditService(),
    )
    result = await service.get_active_roles()
    assert result.items == []


@pytest.mark.asyncio
async def test_get_active_roles_loads_from_repository(monkeypatch):
    locale_id = uuid4()
    role = RoleListItem(
        id=uuid4(),
        code="admin",
        name="Administrator",
    )

    class ReqCtx:
        resolved_locale_id = locale_id

    monkeypatch.setattr(
        "portal.application.rbac.role_service.get_request_context",
        lambda: ReqCtx(),
    )
    repo = StubRoleRepository(active_roles=[role])
    service = RoleService(repo, StubRoleCache(), StubRbacAuditService())
    result = await service.get_active_roles()
    assert len(result.items) == 1
    assert result.items[0].code == "admin"
    assert repo.list_active_called is True


@pytest.mark.asyncio
async def test_init_user_roles_cache_superuser(monkeypatch):
    user_id = uuid4()
    user = UserSensitive(
        id=user_id,
        email="admin@example.com",
        verified=True,
        is_active=True,
        is_superuser=True,
        is_admin=True,
    )
    repo = StubRoleRepository()
    cache = StubRoleCache()
    service = RoleService(repo, cache, StubRbacAuditService())
    codes = await service.init_user_roles_cache(user=user, expire=3600)
    assert codes == ["superadmin"]
    assert user_id in cache.cleared_user_ids
    assert len(cache.init_calls) == 1
    assert repo.list_user_role_codes_called is False


@pytest.mark.asyncio
async def test_init_user_roles_cache_regular_user(monkeypatch):
    user_id = uuid4()
    user = UserSensitive(
        id=user_id,
        email="user@example.com",
        verified=True,
        is_active=True,
        is_superuser=False,
        is_admin=True,
    )
    repo = StubRoleRepository(user_role_codes=["editor", "viewer"])
    cache = StubRoleCache()
    service = RoleService(repo, cache, StubRbacAuditService())
    codes = await service.init_user_roles_cache(user=user, expire=3600)
    assert codes == ["editor", "viewer"]
    assert repo.list_user_role_codes_called is True
    assert cache.init_calls[0][1] == ["editor", "viewer"]


@pytest.mark.asyncio
async def test_init_user_roles_cache_clears_when_no_roles(monkeypatch):
    user_id = uuid4()
    user = UserSensitive(
        id=user_id,
        email="user@example.com",
        verified=True,
        is_active=True,
        is_superuser=False,
        is_admin=True,
    )
    repo = StubRoleRepository(user_role_codes=[])
    cache = StubRoleCache()
    service = RoleService(repo, cache, StubRbacAuditService())
    codes = await service.init_user_roles_cache(user=user, expire=3600)
    assert codes is None
    assert user_id in cache.cleared_user_ids
    assert len(cache.init_calls) == 0
