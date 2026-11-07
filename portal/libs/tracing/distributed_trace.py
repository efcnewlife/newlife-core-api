"""
Vendor-neutral tracing decorator backed by the selected TelemetryBackend.
"""

import functools
import inspect
from collections.abc import Callable
from typing import ParamSpec, TypeVar, overload

from portal.libs.telemetry import get_telemetry_backend

P = ParamSpec("P")
R = TypeVar("R")

SPAN_PARAM = "_span"


def _require_span_parameter(func: Callable[..., object]) -> None:
    parameter = inspect.signature(func).parameters.get(SPAN_PARAM)
    if parameter is None:
        raise TypeError(f"{func.__qualname__} uses inject_span=True but has no keyword-only '{SPAN_PARAM}: TraceSpan' parameter")
    if parameter.kind is not inspect.Parameter.KEYWORD_ONLY:
        raise TypeError(f"{func.__qualname__} '{SPAN_PARAM}' must be keyword-only")


def _reject_caller_span(func: Callable[..., object], kwargs: dict[str, object]) -> None:
    if SPAN_PARAM in kwargs:
        raise TypeError(f"{SPAN_PARAM} is reserved for distributed_trace injection; callers must omit it when calling {func.__qualname__}")


@overload
def distributed_trace(name: str | None = None, *, inject_span: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]: ...


def distributed_trace(name: str | None = None, *, inject_span: bool = False) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """
    Decorate a sync or async function with one backend span for the operation.

    Existing call sites keep working. Pass inject_span=True and a keyword-only
    `_span: TraceSpan = NOOP_SPAN` parameter to annotate the same span the decorator created.
    :param name: Optional stable operation name; defaults to the function's qualname
    :param inject_span: When True, inject the decorator's span as `_span`
    :return:
    """

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inject_span:
            _require_span_parameter(func)
        operation_name = name or func.__qualname__

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                _reject_caller_span(func, kwargs)
                with get_telemetry_backend().start_span(operation_name) as span:
                    if inject_span:
                        kwargs = {**kwargs, SPAN_PARAM: span}
                    return await func(*args, **kwargs)  # type: ignore[misc]

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            _reject_caller_span(func, kwargs)
            with get_telemetry_backend().start_span(operation_name) as span:
                if inject_span:
                    kwargs = {**kwargs, SPAN_PARAM: span}
                return func(*args, **kwargs)

        return sync_wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["SPAN_PARAM", "distributed_trace"]
