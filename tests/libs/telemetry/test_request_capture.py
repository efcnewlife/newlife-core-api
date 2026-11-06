"""
Request failure capture: route templates never carry raw path values.
"""

from uuid import uuid4

import pytest
import sentry_sdk
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient

from portal.config import settings
from portal.libs.telemetry import capture_request_failure, init_sentry
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


def _application() -> FastAPI:
    router = APIRouter(prefix="/items")

    @router.get("/{item_id}/notes/{note_id}")
    async def failing_route(item_id: str, note_id: int):
        raise RuntimeError("synthetic")

    inner = FastAPI()
    inner.include_router(router, prefix="/api/v1")

    @inner.exception_handler(Exception)
    async def handler(request: Request, exc: Exception):
        capture_request_failure(request, exc)
        raise exc

    outer = FastAPI()
    outer.mount("/admin", inner)
    return outer


@pytest.mark.parametrize("raw_item_id", [str(uuid4()).upper(), "jane%40example.com"])
def test_transaction_uses_route_template_for_non_canonical_values(raw_item_id: str):
    transport = CapturingTransport()
    config = settings.model_copy(update={"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN})
    assert init_sentry(config, transport=transport) is True

    response = TestClient(_application(), raise_server_exceptions=False).get(f"/admin/api/v1/items/{raw_item_id}/notes/007")

    assert response.status_code == 500
    sentry_sdk.flush()
    [event] = transport.events
    assert event["transaction"] == "/admin/api/v1/items/{item_id}/notes/{note_id}"
