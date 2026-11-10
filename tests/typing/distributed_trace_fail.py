"""
Rejected static shapes for distributed_trace and TraceSpan (must fail type-check).
"""

from __future__ import annotations

from portal.libs.telemetry import NOOP_SPAN, TraceSpan
from portal.libs.tracing import distributed_trace


@distributed_trace()
def ordinary_sync(value: int) -> str:
    return str(value)


@distributed_trace(inject_span=True)
def injected_sync(value: int, *, _span: TraceSpan = NOOP_SPAN) -> int:
    return value


def rejected_calls() -> None:
    ordinary_sync("bad")
    injected_sync(1, _span=object())
    NOOP_SPAN.set_attribute("synthetic.payload", {"a": 1})
    NOOP_SPAN.set_attribute("synthetic.list", [1, 2])
