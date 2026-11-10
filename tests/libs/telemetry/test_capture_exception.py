"""
Handled-exception reporting through the selected telemetry backend.
"""

import logging
from uuid import uuid4

import pytest
import sentry_sdk

from portal.config import Configuration, settings
from portal.libs.telemetry import NoOpBackend, SentryBackend, capture_exception, select_telemetry_backend
from portal.libs.tracing import distributed_trace
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


def _config(**overrides) -> Configuration:
    values = {"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN}
    values.update(overrides)
    return settings.model_copy(update=values)


def test_capture_exception_sends_one_sanitized_error_under_sentry():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    marker = f"secret-{uuid4().hex}@example.com"
    try:
        raise RuntimeError(marker)
    except RuntimeError as exc:
        capture_exception(exc)

    sentry_sdk.flush()
    [event] = transport.events
    assert event["exception"]["values"][0]["type"] == "RuntimeError"
    assert "value" not in event["exception"]["values"][0]
    assert marker not in str(event)
    assert "request" not in event
    assert event.get("user") in (None, {})


def test_capture_exception_is_a_noop_when_noop_backend_is_selected():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"), transport=transport), NoOpBackend)

    try:
        raise RuntimeError("synthetic")
    except RuntimeError as exc:
        capture_exception(exc)

    sentry_sdk.flush()
    assert transport.envelopes == []


def test_capture_exception_reports_once_when_called_twice_and_when_logged():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    try:
        raise RuntimeError("synthetic")
    except RuntimeError as exc:
        logging.getLogger("tests.telemetry").exception("handled failure")
        capture_exception(exc)
        capture_exception(exc)

    sentry_sdk.flush()
    assert len(transport.events) == 1


def _bind_stale_user() -> None:
    # Keep identity literals out of the failing test frame so stack source context stays clean.
    sentry_sdk.set_user({"id": "stale-user"})


def test_capture_exception_clears_inherited_user_and_keeps_current_trace():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(SENTRY_TRACES_SAMPLE_RATE=1.0), transport=transport), SentryBackend)

    with sentry_sdk.start_transaction(name="background.operation", op="function"):
        _bind_stale_user()
        try:
            raise RuntimeError("synthetic")
        except RuntimeError as exc:
            capture_exception(exc)

    sentry_sdk.flush()
    [event] = transport.events
    assert event.get("user") in (None, {})
    assert "stale-user" not in str(event.get("user", {}))
    assert event["contexts"]["trace"]["op"] == "function"
    assert event["transaction"] == "background.operation"


def test_capture_exception_transport_failure_does_not_raise():
    class _FailingTransport(CapturingTransport):
        def capture_envelope(self, envelope) -> None:
            raise RuntimeError("transport down")

    assert isinstance(select_telemetry_backend(_config(), transport=_FailingTransport()), SentryBackend)

    try:
        raise RuntimeError("synthetic")
    except RuntimeError as exc:
        capture_exception(exc)


def test_nested_decorated_layers_do_not_report_without_explicit_capture():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(SENTRY_TRACES_SAMPLE_RATE=1.0), transport=transport), SentryBackend)

    @distributed_trace()
    def child() -> None:
        raise RuntimeError("synthetic")

    @distributed_trace("parent.operation")
    def parent() -> None:
        child()

    with pytest.raises(RuntimeError, match="synthetic"):
        parent()

    sentry_sdk.flush()
    assert transport.events == []
