"""
Rate limiting through the assembled public application: a burst gets 429 before any other Redis or PostgreSQL work.
"""

import asyncio
from collections import defaultdict
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import portal.libs.depends.rate_limiters as rate_limiters_module
from portal.application.auth.results import UserSensitive
from portal.application.locale.locale_service import LocaleService
from portal.apps import get_public_application
from portal.container import Container
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.database import PostgresConnection
from portal.libs.depends.rate_limiters import attach_rate_limiters, create_redis_rate_limiters, get_rate_limiters_config
from portal.providers.jwt_provider import JWTProvider
from tests.fixtures.app.offline import offline_app  # noqa: F401
from tests.fixtures.telemetry.sentry_transport import CapturingTransport, reset_sentry_client, sentry_transport  # noqa: F401

pytestmark = pytest.mark.usefixtures("offline_app")

ADMIN_ME = "/admin/api/v1/auth/me"
MEMBER_ME = "/api/v1/auth/me"
PORTAL_ORIGIN = "https://portal-dev.example.test"
SHORT_WINDOW_TIMES = get_rate_limiters_config("default").short.times


class _SlidingWindowScript:
    """In-memory stand-in for the Redis script; the real script runs in tests/integration/test_redis_db0.py."""

    def __init__(self):
        self.calls: list[str] = []
        self._accepted: dict[str, list[int]] = defaultdict(list)

    async def __call__(self, keys=None, args=None):
        [key] = keys
        self.calls.append(key)
        now, _member, *windows = args
        accepted = self._accepted[key]
        if any(sum(at >= now - interval for at in accepted) >= times for interval, times in zip(windows[::2], windows[1::2])):
            return 0
        accepted.append(now)
        return 1


class _UnreachableScript:
    async def __call__(self, keys=None, args=None):
        raise ConnectionError("limiter Redis is down")


class _ScriptRedis:
    def __init__(self, script):
        self.script = script

    def register_script(self, script: str):
        return self.script


@pytest.fixture
def client():
    with TestClient(get_public_application(Container()), raise_server_exceptions=False, client=("198.51.100.20", 50000)) as test_client:
        yield test_client


def _attach(client: TestClient, script):
    attach_rate_limiters(client.app, asyncio.run(create_redis_rate_limiters(_ScriptRedis(script))))
    return script


@pytest.fixture
def limiter(client, monkeypatch) -> _SlidingWindowScript:
    """Real limiters with a frozen clock, so a slow test run never leaves the short window."""
    monkeypatch.setattr(rate_limiters_module, "time_ns", lambda: 1_795_000_000_000_000_000)
    return _attach(client, _SlidingWindowScript())


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_a_burst_beyond_the_short_window_gets_429(client, limiter, path):
    statuses = [client.get(path).status_code for _ in range(SHORT_WINDOW_TIMES + 3)]

    assert statuses == [401] * SHORT_WINDOW_TIMES + [429] * 3


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME, "/admin/api/v1/system/settings"])
def test_each_request_is_counted_once(client, limiter, path):
    client.get(path)

    assert limiter.calls == [f"newlife-core-api:rate_limiter:default:198.51.100.20:{path}"]


@pytest.fixture
def request_work(client, monkeypatch) -> list[str]:
    """The per-request work that costs Redis or PostgreSQL connections, in call order."""
    work: list[str] = []
    get_locale_snapshot = LocaleService.get_locale_snapshot
    verify_token = JWTProvider.verify_token

    async def _record_locale(self):
        work.append("locale")
        return await get_locale_snapshot(self)

    def _record_auth(self, *args, **kwargs):
        work.append("auth")
        return verify_token(self, *args, **kwargs)

    async def _record_connection(_self, *_args, **_kwargs):
        work.append("postgres")
        raise OSError("no database in unit tests")

    monkeypatch.setattr(LocaleService, "get_locale_snapshot", _record_locale)
    monkeypatch.setattr(JWTProvider, "verify_token", _record_auth)
    monkeypatch.setattr(PostgresConnection, "create_connection", _record_connection)
    return work


def _admin_headers() -> dict[str, str]:
    user = UserSensitive(id=uuid4(), email="admin@example.test", first_name="A", last_name="B", verified=True, is_active=True, is_admin=True)
    token = JWTProvider(token_blacklist_provider=None).create_access_token(user=user, family_id=uuid4(), aud_type=AccessTokenAudType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


def test_a_rejected_request_costs_one_limiter_call_and_nothing_else(client, limiter, request_work):
    headers = _admin_headers()
    for _ in range(SHORT_WINDOW_TIMES):
        assert client.get(ADMIN_ME, headers=headers).status_code != 429
    assert {"locale", "auth", "postgres"} <= set(request_work)
    request_work.clear()
    limiter.calls.clear()

    response = client.get(ADMIN_ME, headers=headers)

    assert response.status_code == 429
    assert response.json() == {"detail": "Too Many Requests"}
    assert request_work == []
    assert len(limiter.calls) == 1


@pytest.mark.parametrize("path", [ADMIN_ME, MEMBER_ME])
def test_a_cross_origin_429_carries_cors_headers(client, limiter, path):
    headers = {"origin": PORTAL_ORIGIN}
    responses = [client.get(path, headers=headers) for _ in range(SHORT_WINDOW_TIMES + 1)]

    assert responses[-1].status_code == 429
    assert responses[-1].headers["access-control-allow-origin"] in (PORTAL_ORIGIN, "*")


@pytest.mark.parametrize(
    ("method", "path", "headers"),
    [
        pytest.param("OPTIONS", ADMIN_ME, {"origin": PORTAL_ORIGIN, "access-control-request-method": "GET"}, id="admin-preflight"),
        pytest.param("OPTIONS", MEMBER_ME, {"origin": PORTAL_ORIGIN, "access-control-request-method": "GET"}, id="member-preflight"),
        pytest.param("OPTIONS", ADMIN_ME, {}, id="plain-options"),
        pytest.param("GET", "/healthz", {}, id="healthz"),
    ],
)
def test_preflight_and_liveness_are_never_limited(client, limiter, method, path, headers):
    statuses = {client.request(method, path, headers=headers).status_code for _ in range(SHORT_WINDOW_TIMES + 3)}

    assert 429 not in statuses
    assert limiter.calls == []


def _error_types(transport: CapturingTransport) -> list[str]:
    return [event["exception"]["values"][-1]["type"] for event in transport.events if event.get("exception")]


def test_a_failing_limiter_lets_the_request_through_and_reports_to_sentry(sentry_transport, client):  # noqa: F811
    _attach(client, _UnreachableScript())

    response = client.get(ADMIN_ME)

    assert response.status_code == 401
    assert _error_types(sentry_transport) == ["ConnectionError"]


def test_no_limiters_attached_lets_requests_through(client):
    statuses = {client.get(ADMIN_ME).status_code for _ in range(SHORT_WINDOW_TIMES + 3)}

    assert statuses == {401}
