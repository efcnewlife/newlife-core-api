"""
Exhausted connection pools through the assembled public application: 503 with Retry-After, never 500.
"""

import asyncio
from uuid import uuid4

import asyncpg
import pytest
from dependency_injector import providers
from fastapi.testclient import TestClient

from portal.application.auth.results import UserSensitive
from portal.application.locale.locale_service import LocaleService
from portal.apps import get_public_application
from portal.container import Container
from portal.exceptions.responses import ApiBaseException
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.database import PostgresConnection, RedisPool, aio_orm, aio_redis
from portal.providers.jwt_provider import JWTProvider
from tests.fixtures.app.offline import offline_app  # noqa: F401
from tests.fixtures.telemetry.sentry_transport import reset_sentry_client, sentry_transport  # noqa: F401

# Bound before offline_app replaces it.
get_locale_snapshot = LocaleService.get_locale_snapshot

pytestmark = pytest.mark.usefixtures("offline_app")

ADMIN_ME = "/admin/api/v1/auth/me"
ADMIN_LOGIN = "/admin/api/v1/auth/login"
MEMBER_ME = "/api/v1/auth/me"
PORTAL_ORIGIN = "https://portal-dev.example.test"
LOGIN_BODY = {"email": "nobody@example.com", "password": "wrong"}


@pytest.fixture
def client():
    with TestClient(get_public_application(Container()), raise_server_exceptions=False) as test_client:
        yield test_client


def _admin_headers() -> dict[str, str]:
    user = UserSensitive(id=uuid4(), email="admin@example.test", first_name="A", last_name="B", verified=True, is_active=True, is_admin=True)
    token = JWTProvider(token_blacklist_provider=None).create_access_token(user=user, family_id=uuid4(), aud_type=AccessTokenAudType.ADMIN)
    return {"Authorization": f"Bearer {token}", "Origin": PORTAL_ORIGIN}


def _assert_service_unavailable(response) -> None:
    assert response.status_code == 503
    assert response.headers["retry-after"] == "5"
    assert response.json() == {"detail": "Service Unavailable"}
    assert response.headers["access-control-allow-origin"] in (PORTAL_ORIGIN, "*")


class _BusyPool:
    """Every connection is in use; honors the acquire timeout like asyncpg does."""

    async def acquire(self, *, timeout=None):
        await asyncio.wait_for(asyncio.Event().wait(), timeout)


class _FullServerPool:
    async def acquire(self, *, timeout=None):
        raise asyncpg.TooManyConnectionsError("remaining connection slots are reserved")


@pytest.mark.parametrize("pool", [_BusyPool(), _FullServerPool()], ids=["acquire-timeout", "too-many-connections"])
def test_exhausted_postgres_during_authentication_gets_503(client, monkeypatch, pool):
    async def _pool(_self, *_args, **_kwargs):
        return pool

    monkeypatch.setattr(aio_orm, "POOL_ACQUIRE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(PostgresConnection, "create_connection", _pool)

    _assert_service_unavailable(client.get(ADMIN_ME, headers=_admin_headers()))


@pytest.mark.parametrize("path", ["/healthz", ADMIN_ME, MEMBER_ME])
def test_exhausted_redis_during_the_locale_lookup_gets_503(client, monkeypatch, path):
    create = RedisPool.create

    def _exhausted(self):
        redis = create(self)
        while len(redis.connection_pool._in_use_connections) < redis.connection_pool.max_connections:
            redis.connection_pool.get_available_connection()
        return redis

    monkeypatch.setattr(aio_redis, "POOL_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(RedisPool, "create", _exhausted)
    monkeypatch.setattr(LocaleService, "get_locale_snapshot", get_locale_snapshot)

    _assert_service_unavailable(client.get(path, headers={"Origin": PORTAL_ORIGIN}))


class _FailingLoginService:
    def __init__(self, error: Exception, wrap: bool = False):
        self._error = error
        self._wrap = wrap

    async def login_with_password(self, command):
        try:
            raise self._error
        except Exception as error:
            if self._wrap:
                # Services turn unexpected errors into this.
                raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
            raise


@pytest.fixture
def login_failing_with(client):
    def _login(*args, **kwargs):
        client.app.container.login_service.override(providers.Object(_FailingLoginService(*args, **kwargs)))
        return client.post(ADMIN_LOGIN, json=LOGIN_BODY, headers={"Origin": PORTAL_ORIGIN})

    yield _login
    client.app.container.login_service.reset_override()


@pytest.mark.parametrize("wrap", [False, True], ids=["raised", "wrapped-by-service"])
def test_exhausted_pool_inside_an_endpoint_gets_503(login_failing_with, wrap):
    _assert_service_unavailable(login_failing_with(asyncpg.TooManyConnectionsError("sorry, too many clients already"), wrap=wrap))


@pytest.mark.parametrize("error", [TimeoutError("slow query"), ConnectionError("refused")], ids=["query-timeout", "connection-refused"])
@pytest.mark.parametrize("wrap", [False, True], ids=["raised", "wrapped-by-service"])
def test_other_failures_stay_500(login_failing_with, error, wrap):
    assert login_failing_with(error, wrap=wrap).status_code == 500


@pytest.mark.parametrize("wrap", [False, True], ids=["raised", "wrapped-by-service"])
def test_exhausted_pool_is_reported_once(sentry_transport, login_failing_with, wrap):  # noqa: F811
    login_failing_with(asyncpg.TooManyConnectionsError("sorry, too many clients already"), wrap=wrap)

    [event] = [event for event in sentry_transport.events if event.get("exception")]
    assert event["transaction"] == ADMIN_LOGIN
