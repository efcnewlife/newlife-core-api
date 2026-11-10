"""
EventBus reports handled handler failures through the selected telemetry backend.
"""

import pytest
import sentry_sdk

from portal.config import settings
from portal.events.base import BaseEvent, EventHandler
from portal.events.bus import EventBus
from portal.libs.telemetry import NoOpBackend, SentryBackend, select_telemetry_backend
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


class _ProbeEvent(BaseEvent):
    pass


class _FailingHandler(EventHandler):
    @property
    def event_type(self) -> type[BaseEvent]:
        return _ProbeEvent

    async def handle(self, event: BaseEvent) -> None:
        raise RuntimeError("handler failed")


@pytest.mark.asyncio
async def test_event_bus_reports_handler_failure_once_and_still_raises():
    transport = CapturingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN})
    assert isinstance(select_telemetry_backend(config, transport=transport), SentryBackend)

    bus = EventBus()
    bus.subscribe(_ProbeEvent, _FailingHandler())

    with pytest.raises(RuntimeError, match="handler failed"):
        await bus._execute_handler(_FailingHandler(), _ProbeEvent())

    sentry_sdk.flush()
    assert len(transport.events) == 1
    assert transport.events[0]["exception"]["values"][0]["type"] == "RuntimeError"


@pytest.mark.asyncio
async def test_event_bus_noop_exports_nothing_on_handler_failure():
    transport = CapturingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN, "TELEMETRY_BACKEND": "noop"})
    assert isinstance(select_telemetry_backend(config, transport=transport), NoOpBackend)

    with pytest.raises(RuntimeError, match="handler failed"):
        await EventBus()._execute_handler(_FailingHandler(), _ProbeEvent())

    sentry_sdk.flush()
    assert transport.envelopes == []
