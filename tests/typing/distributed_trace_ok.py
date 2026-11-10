"""
Accepted static shapes for distributed_trace and TraceSpan (must type-check clean).
"""

from __future__ import annotations

from typing import assert_type

from portal.libs.telemetry import NOOP_SPAN, SpanAttributeValue, TraceSpan
from portal.libs.tracing import distributed_trace


@distributed_trace()
def ordinary_sync(value: int) -> str:
    return str(value)


@distributed_trace("named.operation")
async def ordinary_async(value: int) -> str:
    return str(value)


@distributed_trace(inject_span=True)
def injected_sync(value: int, *, _span: TraceSpan = NOOP_SPAN) -> int:
    _span.set_attribute("synthetic.count", value)
    return value


@distributed_trace(inject_span=True)
async def injected_async(value: int, *, _span: TraceSpan = NOOP_SPAN) -> int:
    _span.set_attribute("synthetic.count", value)
    return value


def accepted_calls() -> None:
    assert_type(ordinary_sync(1), str)
    assert_type(injected_sync(2), int)
    span: TraceSpan = NOOP_SPAN
    span.set_attribute("synthetic.flag", True)
    span.set_attribute("synthetic.ratio", 0.5)
    value: SpanAttributeValue = "ok"
    span.set_attribute("synthetic.label", value)


async def accepted_async_calls() -> None:
    assert_type(await ordinary_async(1), str)
    assert_type(await injected_async(2), int)
