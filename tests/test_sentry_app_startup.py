"""
Application composition with Sentry: startup and health stay usable whether telemetry is on or off.
"""

import pytest
import sentry_sdk
from fastapi.testclient import TestClient

from portal.apps import get_public_application
from portal.config import settings
from portal.container import Container
from portal.libs.telemetry import capture_diagnostic_event, init_sentry
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


@pytest.fixture
def stg_sentry_settings(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)


def test_disabled_telemetry_leaves_public_application_healthy():
    application = get_public_application(Container())

    assert sentry_sdk.is_initialized() is False
    assert TestClient(application).get("/healthz").json() == {"message": "ok"}


def test_composition_initializes_sentry_from_settings(stg_sentry_settings, monkeypatch):
    # Closed local port: the real HTTP transport never reaches Sentry.
    monkeypatch.setattr(settings, "SENTRY_DSN", "http://public@127.0.0.1:9/0")

    application = get_public_application(Container())

    assert sentry_sdk.is_initialized() is True
    assert sentry_sdk.get_client().options["environment"] == "stg"
    assert sentry_sdk.get_client().options["release"] == "newlife-core-api@5ba2c79"
    assert TestClient(application).get("/healthz").status_code == 200


def test_enabled_startup_sends_only_the_synthetic_diagnostic(stg_sentry_settings, monkeypatch):
    monkeypatch.setattr(settings, "SENTRY_DSN", TEST_DSN)
    transport = CapturingTransport()
    assert init_sentry(settings, transport=transport) is True

    application = get_public_application(Container())
    assert TestClient(application).get("/healthz").status_code == 200
    sentry_sdk.flush()
    assert transport.envelopes == []

    capture_diagnostic_event()
    [event] = transport.events
    assert event["message"] == "newlife-core-api Sentry diagnostic"
    assert event["release"] == "newlife-core-api@5ba2c79"
