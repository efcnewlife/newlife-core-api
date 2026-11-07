"""
distributed_trace: nested Sentry-native spans, optional injection, NoOp behavior, and fail-open cleanup.
"""

import asyncio
from uuid import uuid4

import pytest
import sentry_sdk

from portal.config import Configuration, settings
from portal.libs.telemetry import NOOP_SPAN, NoOpBackend, SentryBackend, TraceSpan, select_telemetry_backend
from portal.libs.tracing import SPAN_PARAM, distributed_trace
from tests.fixtures.telemetry.sentry_transport import TEST_DSN, CapturingTransport, reset_sentry_client  # noqa: F401

pytestmark = pytest.mark.usefixtures("reset_sentry_client")


def _config(**overrides) -> Configuration:
    values = {"ENV": "stg", "APP_VERSION": "5ba2c79", "SENTRY_ENABLED": True, "SENTRY_DSN": TEST_DSN, "SENTRY_TRACES_SAMPLE_RATE": 1.0}
    values.update(overrides)
    return settings.model_copy(update=values)


def _transactions(transport: CapturingTransport) -> list[dict]:
    sentry_sdk.flush()
    return [item.payload.json for envelope in transport.envelopes for item in envelope.items if item.headers.get("type") == "transaction"]


def test_nested_decorated_operations_share_one_trace_under_sentry():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    @distributed_trace()
    def child(value: int) -> int:
        return value + 1

    @distributed_trace("parent.operation")
    def parent() -> int:
        return child(1)

    assert parent() == 2
    [transaction] = _transactions(transport)
    assert transaction["transaction"] == "parent.operation"
    assert [(span["description"], span["parent_span_id"]) for span in transaction["spans"]] == [
        (child.__qualname__, transaction["contexts"]["trace"]["span_id"])
    ]


@pytest.mark.asyncio
async def test_inject_span_annotates_decorator_span_without_extra_child():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    @distributed_trace(inject_span=True)
    async def annotated(*, _span: TraceSpan = NOOP_SPAN) -> str:
        _span.set_attribute("synthetic.count", 3)
        _span.set_attribute("email", f"leak-{uuid4().hex[:8]}@example.com")
        _span.set_attribute("remark", f"secret-remark-{uuid4().hex[:8]}")
        return "ok"

    assert await annotated() == "ok"
    [transaction] = _transactions(transport)
    assert transaction["spans"] == []
    data = transaction["contexts"]["trace"]["data"]
    assert data["synthetic.count"] == 3
    assert "email" not in data and "remark" not in data
    assert all("@example.com" not in str(value) for value in data.values())
    assert all("secret-remark-" not in str(value) for value in data.values())


def test_caller_supplied_span_is_rejected():
    select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"))

    @distributed_trace(inject_span=True)
    def annotated(*, _span: TraceSpan = NOOP_SPAN) -> None:
        return None

    with pytest.raises(TypeError, match=SPAN_PARAM):
        annotated(**{SPAN_PARAM: NOOP_SPAN})


def test_inject_span_requires_keyword_only_parameter():
    with pytest.raises(TypeError, match="inject_span"):

        @distributed_trace(inject_span=True)
        def missing_span(value: int) -> int:
            return value

    with pytest.raises(TypeError, match="keyword-only"):

        @distributed_trace(inject_span=True)
        def positional_span(_span: TraceSpan = NOOP_SPAN) -> None:
            return None


def test_existing_decorator_call_sites_preserve_return_values_under_noop():
    assert isinstance(select_telemetry_backend(_config(TELEMETRY_BACKEND="noop")), NoOpBackend)

    @distributed_trace()
    def sync_op(value: int) -> int:
        return value * 2

    @distributed_trace("named.async")
    async def async_op(value: int) -> int:
        return value * 3

    assert sync_op(2) == 4
    assert asyncio.run(async_op(2)) == 6


def test_noop_backend_exports_no_transactions_for_decorated_work():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(TELEMETRY_BACKEND="noop"), transport=transport), NoOpBackend)

    @distributed_trace(inject_span=True)
    def annotated(*, _span: TraceSpan = NOOP_SPAN) -> int:
        _span.set_attribute("synthetic.count", 1)
        return 1

    assert annotated() == 1
    sentry_sdk.flush()
    assert transport.envelopes == []


def test_failures_and_cancellation_restore_context_and_preserve_exceptions():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    @distributed_trace()
    def boom() -> None:
        raise ValueError("synthetic-business")

    @distributed_trace()
    def cancel() -> None:
        raise asyncio.CancelledError()

    with pytest.raises(ValueError, match="synthetic-business"):
        boom()
    with pytest.raises(asyncio.CancelledError):
        cancel()

    assert sentry_sdk.get_current_span() is None
    transactions = _transactions(transport)
    assert len(transactions) == 2
    assert all(item["contexts"]["trace"].get("status") == "internal_error" for item in transactions)


@pytest.mark.asyncio
async def test_concurrent_tasks_do_not_share_span_identity():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)
    seen: list[int] = []

    @distributed_trace(inject_span=True)
    async def worker(label: int, *, _span: TraceSpan = NOOP_SPAN) -> int:
        _span.set_attribute("synthetic.label", label)
        seen.append(id(_span))
        await asyncio.sleep(0.01)
        return label

    results = await asyncio.gather(worker(1), worker(2))
    assert sorted(results) == [1, 2]
    assert len(set(seen)) == 2
    transactions = _transactions(transport)
    assert len(transactions) == 2
    labels = sorted(item["contexts"]["trace"]["data"]["synthetic.label"] for item in transactions)
    assert labels == [1, 2]


def test_background_root_does_not_require_http_request():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)

    @distributed_trace("background.sweep")
    def sweep() -> str:
        return "done"

    assert sweep() == "done"
    [transaction] = _transactions(transport)
    assert transaction["transaction"] == "background.sweep"
    assert transaction["contexts"]["trace"]["op"] == "function"


def test_string_attribute_values_are_scrubbed():
    transport = CapturingTransport()
    assert isinstance(select_telemetry_backend(_config(), transport=transport), SentryBackend)
    token = f"Bearer eyJ{uuid4().hex}.payload.sig"

    @distributed_trace(inject_span=True)
    def annotated(*, _span: TraceSpan = NOOP_SPAN) -> None:
        _span.set_attribute("diagnostic.detail", f"token={token}")

    annotated()
    [transaction] = _transactions(transport)
    detail = transaction["contexts"]["trace"]["data"]["diagnostic.detail"]
    assert "Bearer " not in detail
    assert "eyJ" not in detail
    assert "[Filtered]" in detail
