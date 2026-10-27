"""
Sentry capture through the assembled HTTP boundary: one sanitized error per unexpected failure, nothing for 4xx.

Every synthetic secret/PII marker is built at runtime so it never appears in a captured source line.
"""

import asyncio
from uuid import UUID, uuid4

import httpx
import pytest
import sentry_sdk
import sqlalchemy.exc
from dependency_injector import providers
from fastapi.testclient import TestClient

import portal.main
from portal.application.auth.results import UserDetail, UserSensitive
from portal.application.locale.locale_service import LocaleService
from portal.config import settings
from portal.libs.consts.enums import AccessTokenAudType
from portal.libs.logger import logger
from portal.libs.telemetry import init_sentry
from portal.main import app
from portal.providers.jwt_provider import JWTProvider
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")

APP_CODE = "test-booking-app"
PREFERRED_LANGUAGE_PATH = "/api/v1/auth/me/preferred-language"


def _marker(kind: str) -> str:
    return f"{kind}-{uuid4().hex[:12]}"


EMAIL = f"{_marker('jane')}@example.com"
PHONE = "+886 912 " + "345 678"
PASSWORD = _marker("hunter")
SQL_PARAM = _marker("sqlparam")
REMARK = _marker("remark")
QUERY_VALUE = _marker("query")
LOCAL_SECRET = _marker("local")
LOG_SECRET = _marker("logvalue")
FIRST_NAME = _marker("first")
LAST_NAME = _marker("last")
MARKERS = [EMAIL, EMAIL.split("@")[0], PHONE, PASSWORD, SQL_PARAM, REMARK, QUERY_VALUE, LOCAL_SECRET, LOG_SECRET, FIRST_NAME, LAST_NAME]


class FailingDependencyError(RuntimeError):
    """Synthetic unexpected failure whose text and cause chain carry secrets."""


def _raise_leaky_failure() -> None:
    secret_local = LOCAL_SECRET  # noqa: F841 - locals must never be exported
    cause = sqlalchemy.exc.IntegrityError(
        "INSERT INTO auth.user (email, phone) VALUES (%(email)s, %(phone)s)",
        {"email": EMAIL, "phone": PHONE, "remark": REMARK},
        Exception(f"DETAIL: Key (email)=({EMAIL}) already exists. password={PASSWORD}"),
    )
    raise FailingDependencyError(f"failed for {EMAIL} {PHONE} password={PASSWORD} remark={REMARK}") from cause


class StubUserRepository:
    def __init__(self, fail_update: bool = False, barrier: asyncio.Barrier | None = None):
        self._fail_update = fail_update
        self._barrier = barrier

    async def get_detail_by_id(self, user_id):
        return UserDetail(id=user_id, email=EMAIL, phone_number=PHONE, first_name=FIRST_NAME, last_name=LAST_NAME, verified=True, is_active=True)

    async def get_sensitive_by_id(self, user_id):
        return UserSensitive(id=user_id, email=EMAIL, first_name=FIRST_NAME, last_name=LAST_NAME, verified=True, is_active=True, is_admin=True)

    async def locale_exists(self, locale_id):
        return True

    async def update_preferred_locale(self, user_id, preferred_locale_id):
        if self._barrier is not None:
            # Both requests are in flight before either fails.
            await self._barrier.wait()
        if self._fail_update:
            logger.warning("Preferred locale update failed for %s", EMAIL)
            logger.error(f"raw failure email={EMAIL} password={PASSWORD} detail={LOG_SECRET}")
            _raise_leaky_failure()


class StubMemberWebAppRegistry:
    def resolve_app_code(self, origin=None, referer=None):
        return APP_CODE


class FailingLoginService:
    async def login_with_password(self, command):
        _raise_leaky_failure()

    async def admin_profile(self):
        _raise_leaky_failure()


@pytest.fixture(autouse=True)
def wire_application_container():
    """Other tests build their own Container, which rewires Provide markers away from the assembled app."""
    app.container.wire()


@pytest.fixture(autouse=True)
def stub_locale_snapshot(monkeypatch):
    """Avoid Redis/DB during middleware locale resolution."""

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
def transport(monkeypatch) -> CapturingTransport:
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)
    monkeypatch.setattr(settings, "SENTRY_DSN", TEST_DSN)
    capturing = CapturingTransport()
    assert init_sentry(settings, transport=capturing) is True
    return capturing


@pytest.fixture
def client():
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def override_dependencies():
    overridden = []

    def _override(**dependencies):
        for name, value in dependencies.items():
            getattr(app.container, name).override(providers.Object(value))
            overridden.append(name)

    yield _override
    for name in overridden:
        getattr(app.container, name).reset_override()


def _member_headers(user_id) -> dict[str, str]:
    user = UserSensitive(id=user_id, email=EMAIL, first_name=FIRST_NAME, last_name=LAST_NAME, verified=True, is_active=True)
    token = JWTProvider(token_blacklist_provider=None).create_access_token(user=user, family_id=uuid4(), aud_type=AccessTokenAudType.USER, azp=APP_CODE)
    return {"Authorization": f"Bearer {token}"}


def _admin_headers(user_id) -> dict[str, str]:
    user = UserSensitive(id=user_id, email=EMAIL, first_name=FIRST_NAME, last_name=LAST_NAME, verified=True, is_active=True, is_admin=True)
    token = JWTProvider(token_blacklist_provider=None).create_access_token(user=user, family_id=uuid4(), aud_type=AccessTokenAudType.ADMIN)
    return {"Authorization": f"Bearer {token}"}


def _serialized(transport: CapturingTransport) -> str:
    sentry_sdk.flush()
    return "".join(envelope.serialize().decode("utf-8", errors="replace") for envelope in transport.envelopes)


def _logs(transport: CapturingTransport) -> list[dict]:
    sentry_sdk.flush()
    return [log for envelope in transport.envelopes for item in envelope.items if item.type == "log" for log in item.payload.json["items"]]


def _assert_no_markers(serialized: str) -> None:
    for marker in MARKERS:
        assert marker not in serialized
    assert "Bearer " not in serialized and "eyJ" not in serialized


def _put_preferred_language(client: TestClient, headers: dict[str, str]):
    return client.put(f"{PREFERRED_LANGUAGE_PATH}?token={QUERY_VALUE}", json={"preferred_locale_id": str(uuid4()), "remark": REMARK}, headers=headers)


def test_member_api_failure_sends_one_sanitized_error_with_internal_user_id(transport, client, override_dependencies):
    user_id = uuid4()
    override_dependencies(user_repository=StubUserRepository(fail_update=True), member_web_app_registry=StubMemberWebAppRegistry())

    response = _put_preferred_language(client, _member_headers(user_id))

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Internal Server Error"
    serialized = _serialized(transport)
    [event] = transport.events
    assert event["user"] == {"id": str(user_id)}
    assert event["environment"] == "stg"
    assert event["release"] == "newlife-core-api@5ba2c79"
    assert event["transaction"] == PREFERRED_LANGUAGE_PATH
    assert event["tags"]["http.request.method"] == "PUT"
    assert "request" not in event and "extra" not in event
    exception_types = [value["type"] for value in event["exception"]["values"]]
    assert exception_types[-1] == "FailingDependencyError"
    assert "IntegrityError" in exception_types
    frames = [frame for value in event["exception"]["values"] for frame in value.get("stacktrace", {}).get("frames", [])]
    assert frames and all("vars" not in frame for frame in frames)
    _assert_no_markers(serialized)


def test_warning_and_error_logs_are_forwarded_without_values(transport, client, override_dependencies):
    override_dependencies(user_repository=StubUserRepository(fail_update=True), member_web_app_registry=StubMemberWebAppRegistry())

    _put_preferred_language(client, _member_headers(uuid4()))

    logs = _logs(transport)
    bodies = [log["body"] for log in logs]
    assert "Preferred locale update failed for %s" in bodies
    assert any(body.startswith("raw failure email=[Filtered]") for body in bodies)
    assert all(log["level"] in {"warn", "error", "fatal"} for log in logs)
    # INFO request/response body logging from LogRoute never leaves the process.
    assert not any("http.request" in body or "response.body" in body for body in bodies)
    _assert_no_markers(_serialized(transport))


def test_error_and_logs_share_the_request_id(transport, client, override_dependencies):
    override_dependencies(user_repository=StubUserRepository(fail_update=True), member_web_app_registry=StubMemberWebAppRegistry())

    _put_preferred_language(client, _member_headers(uuid4()))

    logs = _logs(transport)
    [event] = transport.events
    request_id = event["tags"]["request_id"]
    assert UUID(request_id)
    assert logs and all(log["attributes"]["request_id"]["value"] == request_id for log in logs)


def test_admin_failure_carries_admin_user_id_only(transport, client, override_dependencies):
    user_id = uuid4()
    override_dependencies(user_repository=StubUserRepository(), login_service=FailingLoginService())

    response = client.get("/admin/api/v1/auth/me", headers=_admin_headers(user_id))

    assert response.status_code == 500
    serialized = _serialized(transport)
    [event] = transport.events
    assert event["user"] == {"id": str(user_id)}
    assert event["transaction"] == "/admin/api/v1/auth/me"
    _assert_no_markers(serialized)


def test_unauthenticated_failure_excludes_request_body_and_user(transport, client, override_dependencies):
    override_dependencies(login_service=FailingLoginService())

    response = client.post(f"/admin/api/v1/auth/login?email={QUERY_VALUE}", json={"email": EMAIL, "password": PASSWORD})

    assert response.status_code == 500
    serialized = _serialized(transport)
    [event] = transport.events
    assert "user" not in event
    _assert_no_markers(serialized)


def test_public_application_failure_sends_one_error(transport, client, monkeypatch):
    def _fail() -> str:
        _raise_leaky_failure()

    monkeypatch.setattr(portal.main, "_render_docs_scope_html", _fail)

    response = client.get("/", auth=(settings.DOCS_BASIC_AUTH_USERNAME, settings.DOCS_BASIC_AUTH_PASSWORD))

    assert response.status_code == 500
    serialized = _serialized(transport)
    [event] = transport.events
    assert event["exception"]["values"][-1]["type"] == "FailingDependencyError"
    _assert_no_markers(serialized)


def test_handled_5xx_response_sends_one_error(transport, client, monkeypatch):
    monkeypatch.setattr(settings, "AZURE_TENANT_ID", None)
    monkeypatch.setattr(settings, "AZURE_APP_CLIENT_ID", None)
    app.container.core.microsoft_oidc_provider.reset()

    response = client.post("/admin/api/v1/auth/login/microsoft", json={"id_token": PASSWORD})

    app.container.core.microsoft_oidc_provider.reset()
    assert response.status_code == 503
    serialized = _serialized(transport)
    [event] = transport.events
    assert event["exception"]["values"][-1]["type"] == "ApiBaseException"
    _assert_no_markers(serialized)


def test_ordinary_4xx_and_business_rejections_send_nothing(transport, client, override_dependencies):
    override_dependencies(user_repository=StubUserRepository(), member_web_app_registry=StubMemberWebAppRegistry())
    headers = _member_headers(uuid4())

    assert client.put(PREFERRED_LANGUAGE_PATH, json={"preferred_locale_id": str(uuid4())}).status_code == 401
    assert client.put(PREFERRED_LANGUAGE_PATH, json={"preferredLocaleId": "x"}, headers=headers).status_code == 422
    assert client.get("/admin/api/v1/does-not-exist").status_code == 404
    assert client.get("/healthz").status_code == 200

    sentry_sdk.flush()
    assert transport.events == []


def test_subsequent_request_does_not_inherit_previous_user(transport, client, override_dependencies):
    override_dependencies(
        user_repository=StubUserRepository(fail_update=True), member_web_app_registry=StubMemberWebAppRegistry(), login_service=FailingLoginService()
    )
    user_id = uuid4()

    assert _put_preferred_language(client, _member_headers(user_id)).status_code == 500
    assert client.post("/admin/api/v1/auth/login", json={"email": EMAIL, "password": PASSWORD}).status_code == 500

    sentry_sdk.flush()
    first, second = transport.events
    assert first["user"] == {"id": str(user_id)}
    assert "user" not in second


@pytest.mark.asyncio
async def test_concurrent_requests_keep_their_own_user(transport, override_dependencies):
    override_dependencies(user_repository=StubUserRepository(fail_update=True, barrier=asyncio.Barrier(2)), member_web_app_registry=StubMemberWebAppRegistry())
    user_ids = [uuid4(), uuid4()]

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as async_client:
        responses = await asyncio.gather(
            *(async_client.put(PREFERRED_LANGUAGE_PATH, json={"preferred_locale_id": str(uuid4())}, headers=_member_headers(user_id)) for user_id in user_ids)
        )

    assert [response.status_code for response in responses] == [500, 500]
    sentry_sdk.flush()
    assert sorted(event["user"]["id"] for event in transport.events) == sorted(str(user_id) for user_id in user_ids)


def test_delivery_failure_preserves_the_response(monkeypatch, client, override_dependencies):
    override_dependencies(user_repository=StubUserRepository(fail_update=True), member_web_app_registry=StubMemberWebAppRegistry())
    headers = _member_headers(uuid4())
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    disabled_response = _put_preferred_language(client, headers)

    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)
    # Closed local port: the real HTTP transport fails delivery without contacting Sentry.
    monkeypatch.setattr(settings, "SENTRY_DSN", "http://public@127.0.0.1:9/0")
    assert init_sentry(settings) is True
    failing_delivery_response = _put_preferred_language(client, headers)
    sentry_sdk.flush(timeout=1)

    assert failing_delivery_response.status_code == disabled_response.status_code == 500
    assert failing_delivery_response.json() == disabled_response.json()
