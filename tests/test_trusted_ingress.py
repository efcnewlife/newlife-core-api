"""
Trusted ingress through the assembled public application: Cloudflare origin-secret checks and one client IP.

The origin secret is built at runtime so it never appears in a captured source line.
"""

import asyncio
from uuid import uuid4

import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient
from pydantic import SecretStr

import portal.application.audit.rbac_audit_service as rbac_audit_service_module
from portal.application.audit.rbac_audit_service import RbacAuditService
from portal.apps import get_public_application
from portal.config import settings
from portal.container import Container
from portal.exceptions.responses import UnauthorizedException
from portal.libs.consts.enums import OperationType
from portal.libs.contexts.request_context import get_request_context
from portal.libs.depends.rate_limiters import attach_rate_limiters, create_redis_rate_limiters
from portal.middlewares import CoreRequestMiddleware, TrustedProxyConfigError
from portal.providers.refresh_token_provider import RefreshTokenProvider
from tests.fixtures.app.offline import offline_app  # noqa: F401

pytestmark = pytest.mark.usefixtures("offline_app")

API_HOST = "api-dev.example.test"
ORIGIN_SECRET = f"origin-{uuid4().hex}"
ADMIN_ME = "/admin/api/v1/auth/me"
ADMIN_LOGIN = "/admin/api/v1/auth/login"
MEMBER_ME = "/api/v1/auth/me"


def _cloudflare_headers(client_ip: str = "203.0.113.7", **extra: str) -> dict[str, str]:
    return {"host": API_HOST, "x-newlife-origin-secret": ORIGIN_SECRET, "cf-connecting-ip": client_ip, **extra}


@pytest.fixture
def cloudflare_mode(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_MODE", "cloudflare")
    monkeypatch.setattr(settings, "CLOUDFLARE_ORIGIN_SECRET", SecretStr(ORIGIN_SECRET))
    monkeypatch.setattr(settings, "APP_FQDN", API_HOST)


@pytest.fixture
def peer() -> tuple[str, int]:
    return ("testclient", 50000)


@pytest.fixture
def client(peer):
    with TestClient(get_public_application(Container()), raise_server_exceptions=False, client=peer) as test_client:
        yield test_client


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_cloudflare_mode_rejects_a_request_without_the_origin_secret(cloudflare_mode, client, path):
    headers = _cloudflare_headers()
    del headers["x-newlife-origin-secret"]

    response = client.get(path, headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def _without(headers: dict[str, str], name: str) -> dict[str, str]:
    return {key: value for key, value in headers.items() if key != name}


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
@pytest.mark.parametrize("client_ip", ["203.0.113.7", "2001:db8::7"])
def test_cloudflare_mode_lets_a_verified_request_reach_the_mounted_app(cloudflare_mode, client, path, client_ip):
    response = client.get(path, headers=_cloudflare_headers(client_ip))

    # The mounted app's own authentication answers, so ingress let it through.
    assert response.status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param(_cloudflare_headers() | {"x-newlife-origin-secret": f"{ORIGIN_SECRET}x"}, id="wrong-secret"),
        pytest.param(_cloudflare_headers() | {"x-newlife-origin-secret": ""}, id="empty-secret"),
        pytest.param(list(_cloudflare_headers().items()) + [("x-newlife-origin-secret", ORIGIN_SECRET)], id="duplicate-secret"),
        pytest.param(_cloudflare_headers() | {"host": "app-newlife-api-stg.azurewebsites.net"}, id="unexpected-host"),
        pytest.param(_without(_cloudflare_headers(), "cf-connecting-ip"), id="missing-client-ip"),
        pytest.param(list(_cloudflare_headers().items()) + [("cf-connecting-ip", "198.51.100.9")], id="duplicate-client-ip"),
        pytest.param(_cloudflare_headers("203.0.113.7, 198.51.100.9"), id="client-ip-list"),
        pytest.param(_cloudflare_headers("not-an-ip"), id="malformed-client-ip"),
        pytest.param(_cloudflare_headers("fe80::1%eth0"), id="zoned-client-ip"),
    ],
)
@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_cloudflare_mode_rejects_an_untrusted_request_before_the_mounted_app(cloudflare_mode, client, headers, path):
    response = client.get(path, headers=headers)

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}


def _preflight_headers(**extra: str) -> dict[str, str]:
    return {"origin": "https://portal-dev.example.test", "access-control-request-method": "GET", **extra}


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_cloudflare_mode_answers_a_verified_cors_preflight(cloudflare_mode, client, path):
    response = client.options(path, headers=_preflight_headers(**_cloudflare_headers()))

    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_cloudflare_mode_rejects_a_cors_preflight_without_the_origin_secret(cloudflare_mode, client, path):
    response = client.options(path, headers=_preflight_headers(**_without(_cloudflare_headers(), "x-newlife-origin-secret")))

    assert response.status_code == 403
    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("method", ["GET", "HEAD"])
def test_cloudflare_mode_keeps_liveness_reachable_without_the_origin_secret(cloudflare_mode, client, method):
    response = client.request(method, "/healthz", headers={"host": "app-newlife-api-stg.azurewebsites.net"})

    # HEAD reaches the app too; the GET-only route answers it with 405, not the ingress 403.
    assert response.status_code == (200 if method == "GET" else 405)


@pytest.mark.parametrize(
    ("method", "path"),
    [("POST", "/healthz"), ("GET", "/healthz/"), ("GET", "/"), ("GET", "/docs"), ("GET", "/openapi.json"), ("GET", "/admin/healthz"), ("GET", "/api/healthz")],
)
def test_cloudflare_mode_liveness_exception_covers_nothing_else(cloudflare_mode, client, method, path):
    response = client.request(method, path, headers={"host": API_HOST, "user-agent": "AlwaysOn", "cf-connecting-ip": "203.0.113.7"})

    assert response.status_code == 403


class _RecordingScript:
    def __init__(self):
        self.keys: list[str] = []

    async def __call__(self, keys=None, args=None):
        self.keys.extend(keys)
        return 1


class _RecordingRedis:
    def __init__(self):
        self.script = _RecordingScript()

    def register_script(self, script: str) -> _RecordingScript:
        return self.script


class _RecordingStatement:
    def __init__(self, rows: list[tuple[str, dict]], model):
        self._rows = rows
        self._model = model

    def values(self, *args, **kwargs):
        self._rows.append((self._model.__name__, args[0] if args else kwargs))
        return self

    def on_conflict_do_update(self, **_kwargs):
        return self

    async def execute(self):
        return None


class _RecordingSession:
    """Captures the rows RefreshTokenProvider writes; no database."""

    def __init__(self):
        self.rows: list[tuple[str, dict]] = []

    def insert(self, model):
        return _RecordingStatement(self.rows, model)


class _AttributingLoginService:
    """Runs the real refresh-token and audit writers inside the login request, then denies the login."""

    def __init__(self):
        self.request_ip = None
        self.session = _RecordingSession()

    async def login_with_password(self, command):
        self.request_ip = get_request_context().ip
        await RefreshTokenProvider(session=self.session).issue(user_id=uuid4(), device_id=uuid4(), family_id=uuid4())
        RbacAuditService().create_log(operation_type=OperationType.UPDATE, record_id=uuid4())
        raise UnauthorizedException(detail="Invalid email or password")


@pytest.fixture
def attribution(client, monkeypatch):
    """Login request with the real rate limiter, request context, refresh-token provider, and audit service."""
    audit_events = []
    monkeypatch.setattr(rbac_audit_service_module, "publish_event_in_background", lambda event: audit_events.append(event))
    redis = _RecordingRedis()
    attach_rate_limiters(client.app, asyncio.run(create_redis_rate_limiters(redis)))
    login_service = _AttributingLoginService()
    client.app.container.login_service.override(providers.Object(login_service))

    def _login(headers):
        response = client.post(ADMIN_LOGIN, json={"email": "nobody@example.com", "password": "wrong"}, headers=headers)
        assert response.status_code == 401
        [limiter_key] = redis.script.keys
        device_ip = next(row["last_ip"] for model, row in login_service.session.rows if model == "AuthDevice")
        token_ip = next(row["ip"] for model, row in login_service.session.rows if model == "AuthRefreshToken")
        [audit_event] = audit_events
        return {
            "rate_limit": limiter_key.removeprefix("newlife-core-api:rate_limiter:default:").removesuffix(f":{ADMIN_LOGIN}"),
            "request": login_service.request_ip,
            "device_last_ip": device_ip,
            "refresh_token_ip": token_ip,
            "audit": audit_event.ip_address,
        }

    yield _login
    client.app.container.login_service.reset_override()


FORGED_FORWARDING = {"x-forwarded-for": "192.0.2.66, 192.0.2.67", "x-real-ip": "192.0.2.68"}


@pytest.mark.parametrize(
    ("client_ip", "canonical"), [("203.0.113.7", "203.0.113.7"), ("2001:DB8:0:0::7", "2001:db8::7"), ("::ffff:203.0.113.7", "203.0.113.7")]
)
def test_cloudflare_mode_attributes_every_consumer_to_the_canonical_connecting_ip(cloudflare_mode, attribution, client_ip, canonical):
    observed = attribution(_cloudflare_headers(client_ip, **FORGED_FORWARDING))

    assert observed == dict.fromkeys(observed, canonical)


@pytest.mark.parametrize(("peer", "canonical"), [(("198.51.100.20", 50000), "198.51.100.20"), (("2001:DB8::20", 50000), "2001:db8::20")])
def test_direct_mode_attributes_every_consumer_to_the_transport_peer(attribution, canonical):
    observed = attribution({**FORGED_FORWARDING, "cf-connecting-ip": "192.0.2.69", "x-newlife-origin-secret": ORIGIN_SECRET})

    assert observed == dict.fromkeys(observed, canonical)


def test_direct_mode_needs_no_origin_secret(client):
    assert client.get(ADMIN_ME).status_code == 401
    assert client.get("/healthz").status_code == 200


@pytest.fixture
def captured_request_headers(monkeypatch):
    """Headers the request context captures, once per request to a mounted app."""
    captured: list[dict[str, str]] = []
    resolve_raw_headers = CoreRequestMiddleware.resolve_raw_headers

    async def _record(self, headers):
        captured.append(dict(headers))
        return await resolve_raw_headers(self, headers)

    monkeypatch.setattr(CoreRequestMiddleware, "resolve_raw_headers", _record)
    return captured


@pytest.mark.parametrize("mode", ["direct", "cloudflare"])
def test_origin_secret_never_reaches_the_application(request, captured_request_headers, client, mode):
    if mode == "cloudflare":
        request.getfixturevalue("cloudflare_mode")

    response = client.get(ADMIN_ME, headers=_cloudflare_headers())

    assert response.status_code == 401
    assert len(captured_request_headers) == 1
    for headers in captured_request_headers:
        assert "x-newlife-origin-secret" not in headers
        assert all(ORIGIN_SECRET not in value for value in headers.values())
    assert ORIGIN_SECRET not in response.text


def test_rejected_request_logs_the_reason_without_header_values(cloudflare_mode, client, caplog):
    forged_secret = f"forged-{uuid4().hex}"

    response = client.get(ADMIN_ME, headers=_cloudflare_headers() | {"x-newlife-origin-secret": forged_secret})

    assert response.status_code == 403
    assert "Rejected request from untrusted ingress: invalid origin secret" in caplog.text
    assert forged_secret not in caplog.text and ORIGIN_SECRET not in caplog.text
    assert forged_secret not in response.text


@pytest.mark.parametrize(
    ("mode", "secret", "host"),
    [
        pytest.param("cloudflare", None, API_HOST, id="missing-secret"),
        pytest.param("cloudflare", "short-but-secret-value", API_HOST, id="short-secret"),
        # App Service passes an unresolved reference through as text, and that text is public in newlife-infra.
        pytest.param(
            "cloudflare", "@Microsoft.KeyVault(VaultName=kv-newlife-stg;SecretName=cloudflare-origin-secret)", API_HOST, id="unresolved-key-vault-reference"
        ),
        pytest.param("cloudflare", " @microsoft.keyvault(SecretUri=https://kv.vault.azure.net/secrets/x/) ", API_HOST, id="unresolved-secret-uri-reference"),
        pytest.param("cloudflare", ORIGIN_SECRET, "", id="missing-host"),
        pytest.param("cloudfare", ORIGIN_SECRET, API_HOST, id="unknown-mode"),
    ],
)
def test_invalid_trusted_proxy_settings_fail_startup_without_printing_the_secret(monkeypatch, mode, secret, host):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_MODE", mode)
    monkeypatch.setattr(settings, "CLOUDFLARE_ORIGIN_SECRET", SecretStr(secret) if secret is not None else None)
    monkeypatch.setattr(settings, "APP_FQDN", host)

    with pytest.raises(TrustedProxyConfigError) as raised:
        get_public_application(Container())

    if secret:
        assert secret not in str(raised.value) and secret not in repr(raised.value)


def test_cloudflare_mode_ignores_whitespace_around_the_configured_secret(cloudflare_mode, monkeypatch):
    monkeypatch.setattr(settings, "CLOUDFLARE_ORIGIN_SECRET", SecretStr(f"{ORIGIN_SECRET}\n"))

    with TestClient(get_public_application(Container()), raise_server_exceptions=False) as client:
        assert client.get(ADMIN_ME, headers=_cloudflare_headers()).status_code == 401
