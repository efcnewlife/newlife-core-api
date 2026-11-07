"""
Vendor-neutral tracing decorator and span types.
"""

from portal.libs.telemetry.backend import NOOP_SPAN, TraceSpan
from portal.libs.tracing.distributed_trace import SPAN_PARAM, distributed_trace

__all__ = ["NOOP_SPAN", "SPAN_PARAM", "TraceSpan", "distributed_trace"]
