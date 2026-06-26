"""
OpenTelemetry distributed trace decorator (no-op passthrough).
"""
import functools
import inspect
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def distributed_trace(_name: str | None = None) -> Callable[[F], F]:
    """
    Decorate a function for distributed tracing.
    Currently a no-op passthrough until OpenTelemetry wiring is enabled.
    :param _name: Optional span name override
    :return:
    """

    def decorator(func: F) -> F:
        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await func(*args, **kwargs)

            return async_wrapper  # type: ignore[misc]

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return sync_wrapper  # type: ignore[misc]

    return decorator
