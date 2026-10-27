"""
Sentry SDK initialization: environment, release, enablement, and failure behavior.
"""

import logging

import pytest
import sentry_sdk
from sentry_sdk import metrics

from portal.config import Configuration, settings
from portal.libs.telemetry import capture_diagnostic_event, init_sentry
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


def _config(**overrides) -> Configuration:
    values = {"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN}
    values.update(overrides)
    return settings.model_copy(update=values)


def test_stg_diagnostic_carries_canonical_environment_and_release():
    transport = CapturingTransport()

    assert init_sentry(_config(), transport=transport) is True
    capture_diagnostic_event()

    [event] = transport.events
    assert event["environment"] == "stg"
    assert event["release"] == "newlife-core-api@5ba2c79"


@pytest.mark.parametrize(
    ("env", "version", "expected_release"),
    [("prod", "0.2.33", "newlife-core-api@0.2.33"), ("dev", "v0.1.0", "newlife-core-api@local"), ("dev", "5ba2c79", "newlife-core-api@local")],
)
def test_release_follows_environment_version_convention(env: str, version: str, expected_release: str):
    transport = CapturingTransport()

    assert init_sentry(_config(ENV=env, APP_VERSION=version), transport=transport) is True
    capture_diagnostic_event()

    [event] = transport.events
    assert event["environment"] == env
    assert event["release"] == expected_release


@pytest.mark.parametrize(
    ("env", "version"),
    [
        ("prod", "v0.1.0"),  # config placeholder default must not ship as a prod release
        ("prod", "5ba2c79"),
        ("prod", "local"),
        ("stg", "0.2.33"),
        ("stg", "local"),
        ("stg", "5ba2c79d0e1f2a3b4c5d6e7f8091a2b3c4d5e6f7"),  # full SHA is not the short-SHA release form
        ("production", "0.2.33"),  # unknown environments are never relabeled as prod
        ("qa", "5ba2c79"),
    ],
)
def test_deployed_or_unknown_environment_without_matching_version_stays_disabled(env: str, version: str):
    transport = CapturingTransport()

    assert init_sentry(_config(ENV=env, APP_VERSION=version), transport=transport) is False
    assert capture_diagnostic_event() is None
    assert transport.envelopes == []


@pytest.mark.parametrize("overrides", [{"SENTRY_ENABLED": False}, {"SENTRY_DSN": None}])
def test_disabled_or_missing_dsn_does_not_export(overrides: dict):
    transport = CapturingTransport()

    assert init_sentry(_config(**overrides), transport=transport) is False
    assert capture_diagnostic_event() is None
    assert transport.envelopes == []


def test_invalid_dsn_with_real_transport_disables_instead_of_raising():
    assert init_sentry(_config(SENTRY_DSN="not-a-dsn")) is False
    assert capture_diagnostic_event() is None


def test_repeated_initialization_keeps_the_first_client():
    first, second = CapturingTransport(), CapturingTransport()

    assert init_sentry(_config(), transport=first) is True
    assert init_sentry(_config(ENV="prod", APP_VERSION="0.2.33"), transport=second) is True
    capture_diagnostic_event()

    [event] = first.events
    assert event["release"] == "newlife-core-api@5ba2c79"
    assert second.envelopes == []


def test_info_logs_traces_metrics_and_locals_are_not_exported_automatically():
    transport = CapturingTransport()
    assert init_sentry(_config(), transport=transport) is True

    logging.getLogger("tests.telemetry").info("password=hunter2")
    with sentry_sdk.start_transaction(name="probe"):
        pass
    metrics.count("probe.count", 1)
    sentry_sdk.flush()
    assert transport.envelopes == []

    def _fail(password: str) -> None:
        raise RuntimeError("synthetic")

    try:
        _fail(password="hunter2")
    except RuntimeError:
        sentry_sdk.capture_exception()
    sentry_sdk.flush()

    [event] = transport.events
    assert event.get("breadcrumbs", {}).get("values", []) == []
    assert "user" not in event and "request" not in event
    frames = event["exception"]["values"][0]["stacktrace"]["frames"]
    assert all("vars" not in frame for frame in frames)


def test_error_logs_are_exported_scrubbed_and_never_as_error_events():
    transport = CapturingTransport()
    assert init_sentry(_config(), transport=transport) is True

    logging.getLogger("tests.telemetry").error("password=hunter2")
    sentry_sdk.flush()

    assert transport.events == []
    [envelope] = transport.envelopes
    [log] = envelope.items[0].payload.json["items"]
    assert log["body"] == "password=[Filtered]"


def test_unreachable_ingestion_does_not_raise():
    # Closed local port: the real HTTP transport fails without contacting Sentry.
    assert init_sentry(_config(SENTRY_DSN="http://public@127.0.0.1:9/0")) is True

    assert capture_diagnostic_event() is not None
    sentry_sdk.flush(timeout=1)
