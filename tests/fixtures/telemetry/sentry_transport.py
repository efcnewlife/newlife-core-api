"""
Test-only Sentry transports: capture envelopes in memory instead of contacting ingestion.
"""

from typing import Any

import pytest
import sentry_sdk
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport

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


@pytest.fixture
def reset_sentry_client():
    """Drop the process-wide Sentry client so each test initializes from scratch."""
    yield
    sentry_sdk.get_client().close()
    sentry_sdk.get_global_scope().set_client(None)
