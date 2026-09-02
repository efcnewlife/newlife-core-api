"""
Tests for MockLoginAuthService.
"""

from uuid import uuid4

import pytest

from portal.application.auth.commands import MockLoginCommand
from portal.application.auth.mock_login_auth_service import MOCK_LOGIN_UNAUTHORIZED_DETAIL, MockLoginAuthService
from portal.application.auth.results import HeaderInfo, MemberLoginResult, MemberProfileResult, TokenResult, UserSensitive
from portal.domain.auth.member_web_app import MemberWebApp, MemberWebAppRegistry
from portal.exceptions.responses import UnauthorizedException
from portal.libs.contexts.request_context import RequestContext, reset_request_context, set_request_context


class StubLoginService:
    def __init__(self):
        self.calls: list[tuple] = []

    async def complete_member_login(self, user, app_code):
        self.calls.append((user, app_code))
        return MemberLoginResult(
            member=MemberProfileResult(
                id=user.id,
                email=user.email or "",
                first_name=user.first_name or "",
                last_name=user.last_name or "",
                preferred_name=user.preferred_name,
                roles=[],
                preferred_locale_id=user.preferred_locale_id,
                last_login_at=user.last_login_at,
            ),
            token=TokenResult(access_token="access", refresh_token="refresh", token_type="bearer", expires_in=900),
        )


class StubUserRepository:
    def __init__(self, user=None):
        self._user = user

    async def get_sensitive_by_email(self, email):
        return self._user


def _registry() -> MemberWebAppRegistry:
    return MemberWebAppRegistry([MemberWebApp(code="facility-booking", origins=frozenset({"http://localhost:5174"}))])


def _set_origin(origin: str = "http://localhost:5174", mock_login_secret: str | None = None):
    return set_request_context(RequestContext(headers=HeaderInfo(origin=origin, mock_login_secret=mock_login_secret)))


@pytest.fixture
def mock_login_settings(monkeypatch):
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_ENABLED", True)
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.ENV", "dev")
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_SECRET", None)
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.TESTING_ACCOUNT_EMAIL_SUFFIX", "@test.local")


@pytest.mark.asyncio
async def test_mock_member_login_happy_path_delegates(mock_login_settings):
    user_id = uuid4()
    user = UserSensitive(id=user_id, email="qa@test.local", verified=True, is_active=True, is_admin=False, first_name="QA")
    login_service = StubLoginService()
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=login_service, member_web_app_registry=_registry())
    token = _set_origin()
    try:
        result = await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)

    assert isinstance(result, MemberLoginResult)
    assert len(login_service.calls) == 1
    assert login_service.calls[0][0].id == user_id
    assert login_service.calls[0][1] == "facility-booking"


@pytest.mark.asyncio
async def test_mock_member_login_rejects_when_disabled(mock_login_settings, monkeypatch):
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_ENABLED", False)
    service = MockLoginAuthService(user_repository=StubUserRepository(), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin()
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_mock_member_login_rejects_in_staging_without_secret_config(mock_login_settings, monkeypatch):
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.ENV", "stg")
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_SECRET", None)
    user = UserSensitive(id=uuid4(), email="qa@test.local", verified=True, is_active=True, is_admin=False)
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin()
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_mock_member_login_rejects_invalid_suffix(mock_login_settings):
    user = UserSensitive(id=uuid4(), email="qa@example.com", verified=True, is_active=True, is_admin=False)
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin()
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@example.com"))
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_mock_member_login_rejects_invalid_secret(mock_login_settings, monkeypatch):
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_SECRET", "expected-secret")
    user = UserSensitive(id=uuid4(), email="qa@test.local", verified=True, is_active=True, is_admin=False)
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin(mock_login_secret="wrong-secret")
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_mock_member_login_accepts_matching_secret(mock_login_settings, monkeypatch):
    monkeypatch.setattr("portal.application.auth.mock_login_auth_service.settings.MOCK_LOGIN_SECRET", "expected-secret")
    user = UserSensitive(id=uuid4(), email="qa@test.local", verified=True, is_active=True, is_admin=False)
    login_service = StubLoginService()
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=login_service, member_web_app_registry=_registry())
    token = _set_origin(mock_login_secret="expected-secret")
    try:
        result = await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)

    assert isinstance(result, MemberLoginResult)
    assert len(login_service.calls) == 1


@pytest.mark.asyncio
async def test_mock_member_login_rejects_unknown_origin(mock_login_settings):
    user = UserSensitive(id=uuid4(), email="qa@test.local", verified=True, is_active=True, is_admin=False)
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin(origin="http://unknown.example")
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_mock_member_login_rejects_inactive_user(mock_login_settings):
    user = UserSensitive(id=uuid4(), email="qa@test.local", verified=True, is_active=False, is_admin=False)
    service = MockLoginAuthService(user_repository=StubUserRepository(user=user), login_service=StubLoginService(), member_web_app_registry=_registry())
    token = _set_origin()
    try:
        with pytest.raises(UnauthorizedException, match=MOCK_LOGIN_UNAUTHORIZED_DETAIL):
            await service.mock_member_login(MockLoginCommand(email="qa@test.local"))
    finally:
        reset_request_context(token)
