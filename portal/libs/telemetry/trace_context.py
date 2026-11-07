"""
Task-local tracing depth and HTTP-root flags.

Sentry's current span can leak across concurrent asyncio tasks; these ContextVars do not.
"""

from contextvars import ContextVar

_span_depth: ContextVar[int] = ContextVar("telemetry_span_depth", default=0)
_http_trace_active: ContextVar[bool] = ContextVar("telemetry_http_trace_active", default=False)


def span_depth() -> int:
    return _span_depth.get()


def push_span_depth() -> object:
    return _span_depth.set(_span_depth.get() + 1)


def reset_span_depth(token: object) -> None:
    _span_depth.reset(token)  # type: ignore[arg-type]


def http_trace_active() -> bool:
    return _http_trace_active.get()


def set_http_trace_active(active: bool) -> object:
    return _http_trace_active.set(active)


def reset_http_trace_active(token: object) -> None:
    _http_trace_active.reset(token)  # type: ignore[arg-type]


def should_open_child_span() -> bool:
    """
    Open a child when this task already owns a decorator span or an HTTP request root.
    :return:
    """
    return span_depth() > 0 or http_trace_active()
