"""
Pending-payment expiry FastAPI lifecycle runner tests.
"""

import asyncio

import pytest
import sentry_sdk

from portal.application.facility.pending_payment_expiry_job import pending_payment_expiry_loop, run_pending_payment_expiry_once
from portal.config import settings
from portal.libs.telemetry import NoOpBackend, SentryBackend, select_telemetry_backend
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401


class _StubSession:
    def __init__(self, events: list[str]):
        self.events = events
        self.commit_calls = 0
        self.rollback_calls = 0
        self.close_calls = 0

    async def commit(self):
        self.commit_calls += 1
        self.events.append("commit")

    async def rollback(self):
        self.rollback_calls += 1
        self.events.append("rollback")

    async def close(self):
        self.close_calls += 1
        self.events.append("close")


class _StubService:
    def __init__(self, events: list[str], *, error: Exception | None = None):
        self.events = events
        self.expire_calls = 0
        self.release_calls = 0
        self._error = error

    async def expire_pending_holds(self):
        self.expire_calls += 1
        self.events.append("expire")
        if self._error:
            raise self._error

    async def release_pending_payment_sweep_lock(self):
        self.release_calls += 1
        self.events.append("unlock")


class _StubContainer:
    def __init__(self, session: _StubSession, service: _StubService):
        self._session = session
        self._service = service

    def db_session(self):
        return self._session

    def recurring_booking_service(self):
        return self._service


@pytest.mark.asyncio
async def test_run_pending_payment_expiry_once_unlocks_after_commit():
    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events)
    await run_pending_payment_expiry_once(_StubContainer(session, service))
    assert service.expire_calls == 1
    assert session.commit_calls == 1
    assert session.rollback_calls == 0
    assert service.release_calls == 1
    assert session.close_calls == 1
    assert events == ["expire", "commit", "unlock", "close"]


@pytest.mark.asyncio
async def test_run_pending_payment_expiry_once_unlocks_after_rollback():
    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events, error=RuntimeError("db down"))
    await run_pending_payment_expiry_once(_StubContainer(session, service))
    assert service.expire_calls == 1
    assert session.commit_calls == 0
    assert session.rollback_calls == 1
    assert service.release_calls == 1
    assert events == ["expire", "rollback", "unlock", "close"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_sentry_client")
async def test_run_pending_payment_expiry_once_reports_sweep_failure_once():
    transport = CapturingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN})
    assert isinstance(select_telemetry_backend(config, transport=transport), SentryBackend)

    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events, error=RuntimeError("db down"))
    await run_pending_payment_expiry_once(_StubContainer(session, service))

    sentry_sdk.flush()
    assert session.rollback_calls == 1
    assert service.release_calls == 1
    assert len(transport.events) == 1
    assert transport.events[0]["exception"]["values"][0]["type"] == "RuntimeError"


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_sentry_client")
async def test_run_pending_payment_expiry_once_noop_exports_nothing_on_failure():
    transport = CapturingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN, "TELEMETRY_BACKEND": "noop"})
    assert isinstance(select_telemetry_backend(config, transport=transport), NoOpBackend)

    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events, error=RuntimeError("db down"))
    await run_pending_payment_expiry_once(_StubContainer(session, service))

    sentry_sdk.flush()
    assert session.rollback_calls == 1
    assert transport.envelopes == []


@pytest.mark.asyncio
@pytest.mark.usefixtures("reset_sentry_client")
async def test_run_pending_payment_expiry_once_keeps_rollback_when_transport_fails():
    class _FailingTransport(CapturingTransport):
        def __init__(self) -> None:
            super().__init__()
            self.failures = 0

        def capture_envelope(self, envelope) -> None:
            self.failures += 1
            if self.failures == 1:
                raise RuntimeError("transport down")

    transport = _FailingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN})
    assert isinstance(select_telemetry_backend(config, transport=transport), SentryBackend)

    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events, error=RuntimeError("db down"))
    await run_pending_payment_expiry_once(_StubContainer(session, service))
    sentry_sdk.flush()

    assert transport.failures >= 1
    assert session.rollback_calls == 1
    assert service.release_calls == 1
    assert session.close_calls == 1
    assert events == ["expire", "rollback", "unlock", "close"]


@pytest.mark.asyncio
async def test_pending_payment_expiry_loop_runs_startup_catch_up():
    events: list[str] = []
    session = _StubSession(events)
    service = _StubService(events)
    stop_event = asyncio.Event()
    stop_event.set()
    await pending_payment_expiry_loop(_StubContainer(session, service), stop_event)
    assert service.expire_calls == 1
    assert session.commit_calls == 1
    assert events == ["expire", "commit", "unlock", "close"]
