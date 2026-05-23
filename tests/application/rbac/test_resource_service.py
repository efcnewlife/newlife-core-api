"""
Tests for ResourceService.
"""
from uuid import uuid4

import pytest

from portal.application.rbac.results import ResourceListResult
from portal.application.rbac.resource_service import ResourceService
from portal.domain.rbac.entities import ResourceItem
from portal.exceptions.responses import NotFoundException, UnauthorizedException
from portal.libs.consts.enums import ResourceType
from portal.application.rbac.commands import ResourceListQueryCommand


class StubResourceRepository:
    def __init__(
        self,
        menu_items=None,
        user_items=None,
        detail=None,
    ):
        self._menu_items = menu_items or []
        self._user_items = user_items or []
        self._detail = detail
        self.list_menus_called = False
        self.list_by_user_called = False

    async def get_by_id(self, resource_id, locale_id):
        return self._detail

    async def list_menus(self, is_deleted, locale_id):
        self.list_menus_called = True
        return self._menu_items

    async def list_by_user_id(self, user_id, locale_id):
        self.list_by_user_called = True
        return self._user_items


class StubRbacAuditService:
    def create_log(self, *args, **kwargs):
        pass


def _admin_user_ctx(monkeypatch, *, user_id=None, is_admin=True, is_superuser=False):
    user_id = user_id or uuid4()

    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.is_admin = is_admin
    ctx.is_superuser = is_superuser
    monkeypatch.setattr(
        "portal.application.rbac.resource_service.get_user_context",
        lambda: ctx,
    )
    return ctx


@pytest.mark.asyncio
async def test_get_resources_raises_unauthorized_for_non_admin(monkeypatch):
    _admin_user_ctx(monkeypatch, is_admin=False)
    service = ResourceService(StubResourceRepository(), StubRbacAuditService())
    with pytest.raises(UnauthorizedException):
        await service.get_resources(ResourceListQueryCommand(deleted=False))


@pytest.mark.asyncio
async def test_get_resource_raises_not_found(monkeypatch):
    monkeypatch.setattr(
        "portal.application.rbac.resource_service.get_request_context",
        lambda: None,
    )
    service = ResourceService(StubResourceRepository(detail=None), StubRbacAuditService())
    with pytest.raises(NotFoundException):
        await service.get_resource(resource_id=uuid4())


@pytest.mark.asyncio
async def test_build_tree_nests_children_by_pid():
    parent_id = uuid4()
    child_id = uuid4()
    parent = ResourceItem(
        id=parent_id,
        pid=None,
        name="Parent",
        key="parent",
        code="parent",
        icon="icon",
        path="/parent",
        type=ResourceType.GENERAL,
        description=None,
        remark=None,
        sequence=1.0,
        is_deleted=False,
    )
    child = ResourceItem(
        id=child_id,
        pid=parent_id,
        name="Child",
        key="child",
        code="child",
        icon="icon",
        path="/child",
        type=ResourceType.GENERAL,
        description=None,
        remark=None,
        sequence=2.0,
        is_deleted=False,
    )
    tree = ResourceService.build_tree([parent, child])
    assert len(tree) == 1
    assert tree[0].id == parent_id
    assert len(tree[0].children) == 1
    assert tree[0].children[0].id == child_id


@pytest.mark.asyncio
async def test_get_user_permission_menus_superuser_uses_all_menus(monkeypatch):
    _admin_user_ctx(monkeypatch, is_superuser=True)
    item = ResourceItem(
        id=uuid4(),
        pid=None,
        name="Dashboard",
        key="dashboard",
        code="dashboard",
        icon="icon",
        path="/",
        type=ResourceType.GENERAL,
        description=None,
        remark=None,
        sequence=1.0,
        is_deleted=False,
    )
    repo = StubResourceRepository(menu_items=[item])
    service = ResourceService(repo, StubRbacAuditService())
    result = await service.get_user_permission_menus()
    assert len(result.items) == 1
    assert result.items[0].code == "dashboard"
    assert repo.list_menus_called is True
    assert repo.list_by_user_called is False
