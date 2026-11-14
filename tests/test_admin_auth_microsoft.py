"""
Admin Microsoft auth route smoke tests (no database).
"""

import pytest
from fastapi.testclient import TestClient

from portal.config import settings
from portal.main import app
from tests.fixtures.app.offline import offline_app  # noqa: F401

pytestmark = pytest.mark.usefixtures("offline_app")


@pytest.fixture(autouse=True)
def isolated_azure_settings(monkeypatch):
    """Clear Azure OIDC settings so tests do not depend on developer machine config."""
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", None)
    monkeypatch.setattr(settings, "AZURE_APP_CLIENT_ID", None)
    app.container.core.microsoft_oidc_provider.reset()
    yield
    app.container.core.microsoft_oidc_provider.reset()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_microsoft_auth_returns_503_when_not_configured(client: TestClient):
    """Without AZURE_* env, exchange must reject as service unavailable."""
    response = client.post("/admin/api/v1/auth/login/microsoft", json={"id_token": "invalid"})
    assert response.status_code == 503


def test_microsoft_auth_rejects_camel_case_id_token(client: TestClient):
    response = client.post("/admin/api/v1/auth/login/microsoft", json={"idToken": "invalid"})
    assert response.status_code == 422


def test_public_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("message") == "ok"


def test_admin_auth_login_validation(client: TestClient):
    """Missing password should yield 422."""
    r = client.post("/admin/api/v1/auth/login", json={"email": "a@b.com"})
    assert r.status_code == 422
