"""
Admin Microsoft auth route smoke tests (no database).
"""
import pytest
from fastapi.testclient import TestClient

from portal.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_microsoft_auth_returns_401_when_not_configured(client: TestClient):
    """Without AZURE_* env, exchange must reject."""
    response = client.post("/admin/api/v1/auth/microsoft", json={"id_token": "invalid"})
    assert response.status_code == 401


def test_microsoft_auth_accepts_id_token_alias(client: TestClient):
    response = client.post("/admin/api/v1/auth/microsoft", json={"idToken": "invalid"})
    assert response.status_code == 401


def test_public_healthz(client: TestClient):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json().get("message") == "ok"


def test_admin_auth_login_validation(client: TestClient):
    """Missing password should yield 422."""
    r = client.post("/admin/api/v1/auth/login", json={"email": "a@b.com"})
    assert r.status_code == 422
