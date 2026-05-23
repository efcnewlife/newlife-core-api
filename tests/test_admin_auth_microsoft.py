"""
Admin Microsoft auth route smoke tests (no database).
"""
import pytest
from fastapi.testclient import TestClient

from portal.application.locale.locale_service import LocaleService
from portal.config import settings
from portal.main import app


@pytest.fixture(autouse=True)
def isolated_azure_settings(monkeypatch):
    """Clear Azure OIDC settings so tests do not depend on developer machine config."""
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", None)
    monkeypatch.setattr(settings, "AZURE_APP_CLIENT_ID", None)
    app.container.core.microsoft_oidc_provider.reset()
    yield
    app.container.core.microsoft_oidc_provider.reset()


@pytest.fixture(autouse=True)
def stub_locale_snapshot(monkeypatch):
    """Avoid Redis/DB during middleware locale resolution in route smoke tests."""

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


def test_microsoft_auth_returns_503_when_not_configured(client: TestClient):
    """Without AZURE_* env, exchange must reject as service unavailable."""
    response = client.post("/admin/api/v1/auth/login/microsoft", json={"id_token": "invalid"})
    assert response.status_code == 503


def test_microsoft_auth_accepts_id_token_alias(client: TestClient):
    response = client.post("/admin/api/v1/auth/login/microsoft", json={"idToken": "invalid"})
    assert response.status_code == 503


def test_public_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("message") == "ok"


def test_admin_auth_login_validation(client: TestClient):
    """Missing password should yield 422."""
    r = client.post("/admin/api/v1/auth/login", json={"email": "a@b.com"})
    assert r.status_code == 422
