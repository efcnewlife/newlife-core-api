"""
Member preferred-language HTTP-contract tests (no database).

Exercises the real auth middleware + router + LoginService stack, stubbing only
the user repository and the member web app registry so no DB/Redis is needed.
"""

from uuid import uuid4

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from portal.application.auth.results import UserDetail, UserSensitive
from portal.libs.consts.enums import AccessTokenAudType
from portal.main import app
from portal.providers.jwt_provider import JWTProvider

APP_CODE = "test-booking-app"


class StubUserRepository:
    def __init__(self, user_detail: UserDetail, existing_locale_ids=None):
        self._user_detail = user_detail
        self._existing_locale_ids = existing_locale_ids or set()
        self.preferred_locale_updates: list = []

    async def get_detail_by_id(self, user_id):
        if user_id == self._user_detail.id:
            return self._user_detail
        return None

    async def locale_exists(self, locale_id):
        return locale_id in self._existing_locale_ids

    async def update_preferred_locale(self, user_id, preferred_locale_id):
        self.preferred_locale_updates.append((user_id, preferred_locale_id))


class StubMemberWebAppRegistry:
    def resolve_app_code(self, origin=None, referer=None):
        return APP_CODE


@pytest.fixture(autouse=True)
def stub_locale_snapshot(monkeypatch):
    """Avoid Redis/DB during middleware locale resolution in route smoke tests."""
    from portal.application.locale.locale_service import LocaleService

    async def _stub_get_locale_snapshot(_self):
        return {
            "active_locales": ["en-US"],
            "default_locale": "en-US",
            "normalized_map": {"en-us": "en-US"},
            "normalized_id_map": {},
            "language_buckets": {"en": ["en-US"]},
        }

    monkeypatch.setattr(LocaleService, "get_locale_snapshot", _stub_get_locale_snapshot)


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def member_user_id():
    return uuid4()


def _issue_member_token(user_id) -> str:
    jwt_provider = JWTProvider(token_blacklist_provider=None)
    user = UserSensitive(id=user_id, email="member@example.com", first_name="Mem", last_name="Ber", verified=True, is_active=True)
    return jwt_provider.create_access_token(user=user, family_id=uuid4(), aud_type=AccessTokenAudType.USER, azp=APP_CODE)


@pytest.fixture
def authenticated_headers(member_user_id):
    token = _issue_member_token(member_user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def stub_repository(member_user_id):
    locale_id = uuid4()
    user_detail = UserDetail(id=member_user_id, email="member@example.com", verified=True, is_active=True)
    repo = StubUserRepository(user_detail=user_detail, existing_locale_ids={locale_id})
    app.container.user_repository.override(providers.Object(repo))
    app.container.member_web_app_registry.override(providers.Object(StubMemberWebAppRegistry()))
    yield repo, locale_id
    app.container.user_repository.reset_override()
    app.container.member_web_app_registry.reset_override()


def test_unauthenticated_request_returns_established_auth_response(client: TestClient):
    response = client.put("/api/v1/auth/me/preferred-language", json={"preferred_locale_id": str(uuid4())})
    assert response.status_code == 401


def test_authenticated_valid_locale_returns_204_and_persists(client: TestClient, authenticated_headers, stub_repository, member_user_id):
    repo, locale_id = stub_repository
    response = client.put("/api/v1/auth/me/preferred-language", json={"preferred_locale_id": str(locale_id)}, headers=authenticated_headers)
    assert response.status_code == 204
    assert repo.preferred_locale_updates == [(member_user_id, locale_id)]


def test_authenticated_invalid_locale_returns_bad_request_and_leaves_preference_unchanged(client: TestClient, authenticated_headers, stub_repository):
    repo, _locale_id = stub_repository
    response = client.put("/api/v1/auth/me/preferred-language", json={"preferred_locale_id": str(uuid4())}, headers=authenticated_headers)
    assert response.status_code == 400
    assert repo.preferred_locale_updates == []
