"""
Telemetry backend contract: one backend owns remote errors, logs, and traces for the process lifetime.

A future Azure backend implements this same contract with its own Azure Monitor pipeline. It must own all three
signals, apply the same privacy policy, and never start a Sentry client or remote handler. It is not implemented here.
"""

from contextlib import contextmanager
from typing import ContextManager, Iterator, Optional, Protocol

from fastapi import Request

SpanAttributeValue = str | int | float | bool


class TraceSpan(Protocol):
    """
    Vendor-neutral handle on the current operation's span.
    """

    def set_attribute(self, key: str, value: SpanAttributeValue) -> None: ...


class NoOpSpan:
    """
    Shared across requests and tasks, so it must stay stateless.
    """

    __slots__ = ()

    def set_attribute(self, key: str, value: SpanAttributeValue) -> None:
        return None


NOOP_SPAN: TraceSpan = NoOpSpan()


@contextmanager
def noop_span() -> Iterator[TraceSpan]:
    yield NOOP_SPAN


class TelemetryBackend(Protocol):
    """
    Implementations must never raise into application work, except for start_span propagating the caller's exception.
    """

    def start(self) -> bool:
        """
        Start the backend's clients and handlers.
        :return: Whether remote delivery is active
        """
        ...

    def flush(self) -> None:
        """
        Deliver buffered telemetry during application shutdown, keeping the backend usable afterwards.
        :return:
        """
        ...

    def capture_request_failure(self, request: Request, exc: Exception) -> None:
        """
        Report an unexpected exception or 5xx response once.
        :param request:
        :param exc:
        :return:
        """
        ...

    def capture_diagnostic_event(self) -> Optional[str]:
        """
        Send a fixed, non-sensitive message to verify the configuration.
        :return: Event id, or None when nothing was sent
        """
        ...

    def start_span(self, name: str) -> ContextManager[TraceSpan]:
        """
        Internal tracing seam for portal.libs.tracing.distributed_trace; business code does not call it directly.
        :param name: Stable operation name
        :return:
        """
        ...


class NoOpBackend:
    """
    No remote delivery. Python logging keeps its local handlers because nothing is installed.
    """

    def start(self) -> bool:
        return False

    def flush(self) -> None:
        return None

    def capture_request_failure(self, request: Request, exc: Exception) -> None:
        return None

    def capture_diagnostic_event(self) -> Optional[str]:
        return None

    def start_span(self, name: str) -> ContextManager[TraceSpan]:
        return noop_span()
