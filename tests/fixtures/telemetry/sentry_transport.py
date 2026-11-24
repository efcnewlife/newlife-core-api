"""
Test-only Sentry transports: capture envelopes in memory instead of contacting ingestion.
"""

from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

from portal.config import settings
from portal.libs.telemetry import SentryBackend, select_telemetry_backend, selection

# Reserved DSN shape; the host is never contacted because tests always pass a transport.
TEST_DSN = "https://public@o0.ingest.invalid/0"


class CapturingTransport(Transport):
    """Keep every envelope the SDK would send."""

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        super().__init__(options)
        self.envelopes: list[Envelope] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        self.envelopes.append(envelope)

    @property
    def events(self) -> list[dict[str, Any]]:
        return [envelope.get_event() for envelope in self.envelopes if envelope.get_event() is not None]


def reset_telemetry_state() -> None:
    """Forget the process-wide client, scope data, and selection, as a restart would. Production has no such path."""
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
    # Outside a request, sentry_sdk.set_user() and friends write to these shared scopes, so later tests would inherit them.
    sentry_sdk.get_isolation_scope().clear()
    sentry_sdk.get_current_scope().clear()
    selection._selected_backend = None


@pytest.fixture
def reset_sentry_client():
    """Run each test as a fresh process: importing portal.main has already selected a backend."""
    reset_telemetry_state()
    yield
    reset_telemetry_state()


@pytest.fixture
def sentry_transport(reset_sentry_client, monkeypatch) -> CapturingTransport:
    """Request before the application is built, because building it selects the telemetry backend."""
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)
    monkeypatch.setattr(settings, "SENTRY_DSN", TEST_DSN)
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(settings, transport=transport), SentryBackend)
    return transport
