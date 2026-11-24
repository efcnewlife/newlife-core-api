"""
Request scope through the assembled public application: each mounted request gets one locale lookup, one DB session, and
one request id; public routes get none.
"""

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

import pytest
import sentry_sdk
from dependency_injector import providers
from fastapi import HTTPException
from fastapi.testclient import TestClient

from portal.application.auth.results import TokenResult
from portal.application.locale.locale_service import LocaleService
from portal.apps import get_public_application
from portal.config import settings
from portal.container import Container
from portal.exceptions.responses import ConflictErrorException
from portal.libs.contexts.request_context import get_request_context
from portal.libs.database.session_proxy import SessionProxy
from portal.middlewares import core_request
from tests.fixtures.app.offline import offline_app  # noqa: F401
from tests.fixtures.telemetry.sentry_transport import CapturingTransport, reset_sentry_client, sentry_transport  # noqa: F401

pytestmark = pytest.mark.usefixtures("offline_app")

ADMIN_REFRESH = "/admin/api/v1/auth/refresh"
MEMBER_REFRESH = "/api/v1/auth/refresh"
ADMIN_ME = "/admin/api/v1/auth/me"
MEMBER_ME = "/api/v1/auth/me"
PUBLIC_PATHS = ["/healthz", "/", "/openapi.json", "/does-not-exist"]
BODY = {"refresh_token": "opaque"}

both_mounted_apps = pytest.mark.parametrize("path", [ADMIN_REFRESH, MEMBER_REFRESH], ids=["admin", "member"])


class _TransactionalSession:
    """Keeps a write only when it is committed, like the real Session."""

    def __init__(self):
        self.pending: list[str] = []
        self.committed: list[str] = []
        self.rolled_back = False
        self.closed = False

    def write(self, row: str) -> None:
        self.pending.append(row)

    async def commit(self) -> None:
        self.committed += self.pending
        self.pending = []

    async def rollback(self) -> None:
        self.pending = []
        self.rolled_back = True

    async def close(self) -> None:
        self.closed = True


class _WritingRefreshTokenService:
    """Writes through the session proxy that repositories use, then optionally fails."""

    def __init__(self):
        self.error: Optional[Exception] = None
        self.request_ids: list[str] = []

    async def refresh_token(self, command) -> TokenResult:
        self.request_ids.append(get_request_context().request_id)
        SessionProxy().write("row")
        if self.error is not None:
            raise self.error
        return TokenResult(access_token="access", refresh_token="refresh", expires_in=900)

    refresh_member_token = refresh_token


@dataclass
class _Probe:
    client: TestClient
    service: _WritingRefreshTokenService
    sessions: list[_TransactionalSession] = field(default_factory=list)
    bound_request_ids: list[str] = field(default_factory=list)
    locale_lookups: list[str] = field(default_factory=list)


@pytest.fixture
def probe(monkeypatch):
    service = _WritingRefreshTokenService()
    application = get_public_application(Container())
    with TestClient(application, raise_server_exceptions=False) as client:
        observed = _Probe(client=client, service=service)

        def _open_session() -> _TransactionalSession:
            observed.sessions.append(_TransactionalSession())
            return observed.sessions[-1]

        get_locale_snapshot = LocaleService.get_locale_snapshot
        bind_request_id = core_request.bind_request_id

        async def _record_locale_lookup(self):
            observed.locale_lookups.append("lookup")
            return await get_locale_snapshot(self)

        def _record_request_id(request, request_id):
            observed.bound_request_ids.append(request_id)
            bind_request_id(request, request_id)

        monkeypatch.setattr(LocaleService, "get_locale_snapshot", _record_locale_lookup)
        monkeypatch.setattr(core_request, "bind_request_id", _record_request_id)
        application.container.db_session.override(providers.Callable(_open_session))
        application.container.refresh_token_service.override(providers.Object(service))
        yield observed


@both_mounted_apps
def test_a_mounted_request_gets_one_locale_lookup_one_session_and_one_request_id(probe, path):
    response = probe.client.post(path, json=BODY)

    assert response.status_code == 200
    assert len(probe.locale_lookups) == 1
    [session] = probe.sessions
    # The handler's write went to the one session that was opened.
    assert session.committed == ["row"]
    assert session.closed
    [request_id] = probe.bound_request_ids
    assert UUID(request_id)
    assert probe.service.request_ids == [request_id]


@both_mounted_apps
def test_an_unhandled_exception_rolls_back_and_never_commits(probe, path):
    probe.service.error = RuntimeError("after a partial write")

    response = probe.client.post(path, json=BODY)

    assert response.status_code == 500
    [session] = probe.sessions
    assert session.committed == []
    assert session.rolled_back
    assert session.closed


@both_mounted_apps
@pytest.mark.parametrize("error", [HTTPException(status_code=409), ConflictErrorException(detail="taken")], ids=["http-exception", "api-exception"])
def test_a_handled_exception_rolls_back(probe, path, error):
    probe.service.error = error

    response = probe.client.post(path, json=BODY)

    assert response.status_code == 409
    assert response.headers["content-language"] == "en-US"
    [session] = probe.sessions
    assert session.committed == []
    assert session.rolled_back
    assert session.closed


@pytest.mark.parametrize(
    ("method", "path", "body", "status"),
    [
        pytest.param("POST", ADMIN_REFRESH, BODY, 200, id="admin-success"),
        pytest.param("POST", MEMBER_REFRESH, BODY, 200, id="member-success"),
        pytest.param("GET", ADMIN_ME, None, 401, id="admin-unauthenticated"),
        pytest.param("GET", MEMBER_ME, None, 401, id="member-unauthenticated"),
        pytest.param("POST", ADMIN_REFRESH, {}, 422, id="admin-invalid-body"),
        pytest.param("POST", MEMBER_REFRESH, {}, 422, id="member-invalid-body"),
        pytest.param("GET", "/admin/api/v1/does-not-exist", None, 404, id="admin-unknown-path"),
        pytest.param("GET", "/api/v1/does-not-exist", None, 404, id="member-unknown-path"),
    ],
)
def test_mounted_responses_carry_the_resolved_content_language(probe, method, path, body, status):
    response = probe.client.request(method, path, json=body)

    assert response.status_code == status
    assert response.headers.get_list("content-language") == ["en-US"]


@pytest.mark.parametrize("path", PUBLIC_PATHS)
def test_public_routes_get_no_request_scope(probe, path):
    response = probe.client.get(path)

    assert response.status_code < 500
    assert "content-language" not in response.headers
    assert probe.locale_lookups == []
    assert probe.sessions == []
    assert probe.bound_request_ids == []


def test_liveness_does_not_depend_on_the_locale_lookup(probe, monkeypatch):
    async def _unreachable(_self):
        raise ConnectionError("Redis is down")

    monkeypatch.setattr(LocaleService, "get_locale_snapshot", _unreachable)

    response = probe.client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"message": "ok"}
    # The lookup really is down for requests that need it.
    assert probe.client.post(ADMIN_REFRESH, json=BODY).status_code == 500


@pytest.fixture
def traces_enabled(monkeypatch):
    """Request before sentry_transport, which starts the SDK."""
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0)


@both_mounted_apps
def test_a_mounted_failure_reports_one_error_and_one_trace_root(traces_enabled, sentry_transport: CapturingTransport, probe, path):  # noqa: F811
    probe.service.error = RuntimeError("boom")

    probe.client.post(path, json=BODY)

    sentry_sdk.flush()
    [error] = [event for event in sentry_transport.events if event.get("exception")]
    assert [error["tags"]["request_id"]] == probe.service.request_ids
    items = [item for envelope in sentry_transport.envelopes for item in envelope.items]
    [root] = [item.payload.json for item in items if item.headers.get("type") == "transaction"]
    assert root["contexts"]["trace"]["op"] == "http.server"
    assert root["transaction"] == path
