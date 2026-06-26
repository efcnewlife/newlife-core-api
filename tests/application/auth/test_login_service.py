"""
Tests for LoginService.
"""
from uuid import uuid4

import pytest

from portal.application.auth.commands import LoginCommand
from portal.application.auth.login_service import LoginService
from portal.application.auth.results import UserSensitive
from portal.exceptions.responses import UnauthorizedException


class StubUserRepository:
    def __init__(self, user=None):
        self._user = user
        self.last_login_updates: list = []

    async def get_sensitive_by_email(self, email):
        return self._user

    async def update_last_login_at(self, user_id, last_login_at):
        self.last_login_updates.append((user_id, last_login_at))


class StubPasswordProvider:
    def __init__(self, valid=True):
        self._valid = valid

    def verify_password(self, password, password_hash):
        return self._valid


class StubJwtProvider:
    def create_access_token(self, **kwargs):
        return "access-token"


class StubRefreshTokenProvider:
    async def issue(self, **kwargs):
        return "refresh-token"


class StubRoleService:
    async def init_user_roles_cache(self, user, expire):
        return ["admin"]


class StubPermissionService:
    async def init_user_permissions_cache(self, user, expire):
        return ["user.read"]


@pytest.mark.asyncio
async def test_login_with_password_invalid_credentials():
    repo = StubUserRepository(user=None)
    service = LoginService(
        user_repository=repo,
        jwt_provider=StubJwtProvider(),
        refresh_token_provider=StubRefreshTokenProvider(),
        password_provider=StubPasswordProvider(),
        role_service=StubRoleService(),
        permission_service=StubPermissionService(),
    )
    with pytest.raises(UnauthorizedException):
        await service.login_with_password(LoginCommand(email="missing@example.com", password="secret"))


@pytest.mark.asyncio
async def test_login_with_password_success(monkeypatch):
    user_id = uuid4()
    user = UserSensitive(
        id=user_id,
        email="admin@example.com",
        verified=True,
        is_active=True,
        is_superuser=False,
        is_admin=True,
        password_hash="hashed",
    )
    repo = StubUserRepository(user=user)
    service = LoginService(
        user_repository=repo,
        jwt_provider=StubJwtProvider(),
        refresh_token_provider=StubRefreshTokenProvider(),
        password_provider=StubPasswordProvider(valid=True),
        role_service=StubRoleService(),
        permission_service=StubPermissionService(),
    )
    result = await service.login_with_password(
        LoginCommand(email="admin@example.com", password="secret"),
    )
    assert result.token.access_token == "access-token"
    assert result.admin.email == "admin@example.com"
    assert len(repo.last_login_updates) == 1
