"""
Telemetry backend selection: one backend per process, resolved once, never silently remote.
"""

import asyncio
import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
import sentry_sdk
from fastapi.testclient import TestClient

from portal.apps import get_public_application
from portal.config import Configuration, settings
from portal.container import Container
from portal.libs.logger import logger
from portal.libs.telemetry import (
    NOOP_SPAN,
    NoOpBackend,
    SentryBackend,
    capture_diagnostic_event,
    flush_telemetry,
    get_telemetry_backend,
    select_telemetry_backend,
)
from portal.main import app
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


@pytest.fixture(autouse=True)
def restore_application_wiring():
    """Building a Container rewires Provide markers away from the assembled app that later test modules use."""
    yield
    app.container.wire()


def _config(**overrides) -> Configuration:
    values = {"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN, "TELEMETRY_BACKEND": None}
    values.update(overrides)
    return settings.model_copy(update=values)


def _enable_sentry_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ENV", "stg")
    monkeypatch.setattr(settings, "APP_VERSION", "5ba2c79")
    monkeypatch.setattr(settings, "SENTRY_ENABLED", True)
    monkeypatch.setattr(settings, "SENTRY_DSN", TEST_DSN)


def _log_items(transport: CapturingTransport) -> list[dict]:
    return [log for envelope in transport.envelopes for item in envelope.items if item.type == "log" for log in item.payload.json["items"]]


@pytest.mark.parametrize(
    "overrides",
    [
        {},  # existing deployments set no backend and keep Sentry
        {"TELEMETRY_BACKEND": ""},
        {"TELEMETRY_BACKEND": "sentry"},
        {"TELEMETRY_BACKEND": "sentry", "ENV": "dev", "APP_VERSION": "v0.1.0"},  # development opt-in
    ],
)
def test_sentry_is_selected_when_requested_and_allowed(overrides: dict):
    transport = CapturingTransport()

    backend = select_telemetry_backend(_config(**overrides), transport=transport)
    capture_diagnostic_event()

    assert isinstance(backend, SentryBackend)
    assert get_telemetry_backend() is backend
    assert len(transport.events) == 1


@pytest.mark.parametrize(
    "overrides",
    [
        {"TELEMETRY_BACKEND": "noop"},  # wins over a fully configured Sentry
        {"TELEMETRY_BACKEND": "sentry", "SENTRY_ENABLED": False},  # explicit disabling still wins
        {"TELEMETRY_BACKEND": "sentry", "SENTRY_DSN": None},
        {"TELEMETRY_BACKEND": "sentry", "ENV": "prod", "APP_VERSION": "v0.1.0"},  # untrustworthy release
        {"TELEMETRY_BACKEND": "azure"},  # known future name, not implemented
        {"TELEMETRY_BACKEND": "Sentry"},  # no guessing at near misses
        {"TELEMETRY_BACKEND": "https://attacker.invalid/0"},
    ],
)
def test_everything_else_selects_noop_without_starting_the_sdk(overrides: dict):
    transport = CapturingTransport()

    backend = select_telemetry_backend(_config(**overrides), transport=transport)
    logging.getLogger("tests.telemetry").error("password=hunter2")

    assert isinstance(backend, NoOpBackend)
    assert sentry_sdk.is_initialized() is False
    assert capture_diagnostic_event() is None
    sentry_sdk.flush()
    assert transport.envelopes == []


def test_unknown_backend_warns_locally_without_echoing_the_value(caplog, monkeypatch):
    caplog.set_level(logging.WARNING, logger=logger.name)
    monkeypatch.setattr(logger, "propagate", True)

    select_telemetry_backend(_config(TELEMETRY_BACKEND="not-a-backend-secret"))

    assert "TELEMETRY_BACKEND" in caplog.text
    assert "not-a-backend-secret" not in caplog.text


@pytest.mark.parametrize("env", ["dev", "stg", "prod"])
@pytest.mark.parametrize("value", ["maybe", ""])
def test_malformed_sentry_flag_disables_sentry_without_breaking_startup(env: str, value: str):
    # A new process: field defaults are computed from the environment when portal.config is first imported.
    result = subprocess.run(
        [sys.executable, "-c", "from portal.config import settings; print(settings.SENTRY_ENABLED)"],
        env={**os.environ, "ENV": env, "SENTRY_ENABLED": value},
        cwd=Path(__file__).resolve().parents[3],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert result.stdout.strip().splitlines()[-1] == "False"


def test_selection_stays_fixed_until_restart():
    first_transport, second_transport = CapturingTransport(), CapturingTransport()

    first = select_telemetry_backend(_config(), transport=first_transport)
    second = select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"), transport=second_transport)
    capture_diagnostic_event()

    assert second is first
    assert len(first_transport.events) == 1
    assert second_transport.envelopes == []


def test_noop_selection_stays_fixed_when_sentry_config_appears_later():
    transport = CapturingTransport()

    first = select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"))
    second = select_telemetry_backend(_config(), transport=transport)

    assert second is first
    assert sentry_sdk.is_initialized() is False
    assert transport.envelopes == []


def test_nothing_is_exported_before_selection():
    assert isinstance(get_telemetry_backend(), NoOpBackend)
    assert capture_diagnostic_event() is None


def test_repeated_app_construction_does_not_accumulate_handlers_or_integrations(monkeypatch):
    transport = CapturingTransport()
    _enable_sentry_settings(monkeypatch)
    backend = select_telemetry_backend(settings, transport=transport)
    client = sentry_sdk.get_client()
    root_handlers = list(logging.getLogger().handlers)
    logger_handlers = list(logger.handlers)
    integrations = set(client.integrations)

    for _ in range(3):
        get_public_application(Container())

    assert get_telemetry_backend() is backend
    assert sentry_sdk.get_client() is client
    assert set(client.integrations) == integrations
    assert logging.getLogger().handlers == root_handlers
    assert logger.handlers == logger_handlers
    logging.getLogger("tests.telemetry").warning("synthetic repeat-construction warning")
    sentry_sdk.flush()
    assert len(_log_items(transport)) == 1


def test_noop_installs_no_remote_integration_and_keeps_local_logging():
    root_handlers = list(logging.getLogger().handlers)
    logger_handlers = list(logger.handlers)
    records: list[logging.LogRecord] = []
    handler = logging.Handler()
    handler.emit = records.append
    local_logger = logging.getLogger("tests.telemetry.local")
    local_logger.addHandler(handler)

    select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"))
    local_logger.warning("still logged locally")

    local_logger.removeHandler(handler)
    assert [record.getMessage() for record in records] == ["still logged locally"]
    assert sentry_sdk.get_client().is_active() is False
    assert logging.getLogger().handlers == root_handlers
    assert logger.handlers == logger_handlers


@pytest.mark.parametrize("overrides", [{}, {"TELEMETRY_BACKEND": "noop"}])
def test_tracing_seam_yields_a_harmless_span_and_exports_nothing(overrides: dict):
    transport = CapturingTransport()
    backend = select_telemetry_backend(_config(**overrides), transport=transport)

    with backend.start_span("synthetic.operation") as span:
        assert span.set_attribute("synthetic.count", 1) is None

    sentry_sdk.flush()
    assert transport.envelopes == []


@pytest.mark.parametrize("overrides", [{}, {"TELEMETRY_BACKEND": "noop"}])
def test_tracing_seam_propagates_exceptions_and_cancellation(overrides: dict):
    backend = select_telemetry_backend(_config(**overrides), transport=CapturingTransport())

    with pytest.raises(ValueError, match="synthetic"), backend.start_span("synthetic.operation"):
        raise ValueError("synthetic")
    with pytest.raises(asyncio.CancelledError), backend.start_span("synthetic.operation"):
        raise asyncio.CancelledError()


def test_unsafe_automatic_tracing_stays_disabled_under_sentry_without_sample_rate():
    transport = CapturingTransport()
    select_telemetry_backend(_config(), transport=transport)

    options = sentry_sdk.get_client().options
    with sentry_sdk.start_transaction(name="probe"):
        pass
    sentry_sdk.flush()

    assert options["traces_sample_rate"] is None
    assert options["traces_sampler"] is None
    assert options["auto_enabling_integrations"] is False
    assert transport.envelopes == []


def test_configured_traces_sample_rate_exports_manual_spans():
    transport = CapturingTransport()
    select_telemetry_backend(_config(SENTRY_TRACES_SAMPLE_RATE=1.0), transport=transport)

    with select_telemetry_backend().start_span("synthetic.operation") as span:
        span.set_attribute("synthetic.count", 1)
    sentry_sdk.flush()

    options = sentry_sdk.get_client().options
    assert options["traces_sample_rate"] == 1.0
    assert options["auto_enabling_integrations"] is False
    transactions = [item.payload.json for envelope in transport.envelopes for item in envelope.items if item.headers.get("type") == "transaction"]
    assert [item["transaction"] for item in transactions] == ["synthetic.operation"]


def test_noop_span_keeps_no_state():
    NOOP_SPAN.set_attribute("synthetic.request", "first")

    assert not hasattr(NOOP_SPAN, "__dict__")
    with pytest.raises(AttributeError):
        NOOP_SPAN.synthetic = "request-state"


def test_application_shutdown_delivers_buffered_logs(monkeypatch):
    transport = CapturingTransport()
    _enable_sentry_settings(monkeypatch)
    monkeypatch.setattr(settings, "REDIS_URL", None)
    select_telemetry_backend(settings, transport=transport)

    with TestClient(get_public_application(Container())):
        logging.getLogger("tests.telemetry").warning("synthetic shutdown warning")
        assert _log_items(transport) == []

    assert [log["body"] for log in _log_items(transport)] == ["synthetic shutdown warning"]


def test_flush_failure_does_not_raise(monkeypatch):
    select_telemetry_backend(_config(), transport=CapturingTransport())

    def _fail(*_args, **_kwargs) -> None:
        raise RuntimeError("synthetic flush failure")

    monkeypatch.setattr(sentry_sdk, "flush", _fail)

    flush_telemetry()


def test_flush_without_selection_is_harmless():
    flush_telemetry()
