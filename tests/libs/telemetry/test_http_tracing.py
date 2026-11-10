"""
HTTP request roots continue supported frontend sentry-trace headers into service spans.
"""

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient

from portal.config import Configuration, settings
from portal.libs.telemetry import SentryBackend, select_telemetry_backend
from portal.libs.tracing import distributed_trace
from portal.middlewares.core_request import CoreRequestMiddleware
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")

PARENT_TRACE_ID = "11111111111111111111111111111111"
PARENT_SPAN_ID = "2222222222222222"


def _config(**overrides) -> Configuration:
    values = {"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN, "SENTRY_TRACES_SAMPLE_RATE": 1.0}
    values.update(overrides)
    return settings.model_copy(update=values)


def _transactions(transport: CapturingTransport) -> list[dict]:
    sentry_sdk.flush()
    return [item.payload.json for envelope in transport.envelopes for item in envelope.items if item.headers.get("type") == "transaction"]


@pytest.fixture
def tracing_app(monkeypatch):
    transport = CapturingTransport()
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)
    monkeypatch.setattr(settings, "SENTRY_DSN", TEST_DSN)
    monkeypatch.setattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 1.0)
    assert isinstance(select_telemetry_backend(settings, transport=transport), SentryBackend)

    @distributed_trace()
    async def service_op() -> dict[str, str]:
        return {"ok": "1"}

    application = FastAPI()

    @application.get("/trace-probe")
    async def trace_probe():
        return await service_op()

    application.add_middleware(CoreRequestMiddleware)

    # Locale resolution hits the container; stub the middleware path used by CoreRequestMiddleware.
    async def _fake_locale_detector(self, accept_language):
        return "en-US", None, ["en-US"]

    monkeypatch.setattr(CoreRequestMiddleware, "locale_detector", _fake_locale_detector)

    class _StubContainer:
        def db_session(self):
            class _Session:
                async def rollback(self):
                    return None

                async def commit(self):
                    return None

                async def close(self):
                    return None

            return _Session()

    application.container = _StubContainer()
    return application, transport


def test_incoming_frontend_trace_continues_into_service_span(tracing_app):
    application, transport = tracing_app
    headers = {
        "sentry-trace": f"{PARENT_TRACE_ID}-{PARENT_SPAN_ID}-1",
        "baggage": (f"sentry-environment=stg,sentry-public_key=public,sentry-trace_id={PARENT_TRACE_ID},sentry-sample_rate=1,sentry-sampled=true"),
    }

    with TestClient(application) as client:
        response = client.get("/trace-probe", headers=headers)

    assert response.status_code == 200
    [transaction] = _transactions(transport)
    assert transaction["contexts"]["trace"]["trace_id"] == PARENT_TRACE_ID
    assert transaction["contexts"]["trace"]["parent_span_id"] == PARENT_SPAN_ID
    assert transaction["transaction"] == "/trace-probe"
    assert transaction["spans"][0]["description"].endswith("service_op")


def test_request_without_trace_headers_still_creates_http_root(tracing_app):
    application, transport = tracing_app

    with TestClient(application) as client:
        assert client.get("/trace-probe").status_code == 200

    [transaction] = _transactions(transport)
    assert len(transaction["contexts"]["trace"]["trace_id"]) == 32
    assert transaction["contexts"]["trace"]["parent_span_id"] is None
    assert transaction["transaction"] == "/trace-probe"
