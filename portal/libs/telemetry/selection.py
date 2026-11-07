"""
Process-wide telemetry backend selection. Resolved once before requests; changing configuration requires a restart.

Precedence (first match wins):
1. TELEMETRY_BACKEND=noop selects NoOpBackend, even with Sentry fully configured.
2. A TELEMETRY_BACKEND value other than empty, sentry, or noop selects NoOpBackend and warns.
3. Empty or sentry selects SentryBackend only if it can start: SENTRY_ENABLED is true, SENTRY_DSN is set, the
   release is valid, and the SDK initializes. Otherwise NoOpBackend is selected.
"""

from typing import ContextManager, Optional

from fastapi import Request
from sentry_sdk.transport import Transport

from portal.config import Configuration, settings
from portal.libs.logger import logger
from portal.libs.telemetry.backend import NoOpBackend, TelemetryBackend
from portal.libs.telemetry.sentry import SentryBackend

BACKEND_SENTRY = "sentry"
BACKEND_NOOP = "noop"

_selected_backend: Optional[TelemetryBackend] = None
# Before selection, nothing is exported.
_UNSELECTED_BACKEND = NoOpBackend()


def _resolve_backend(config: Configuration, transport: Optional[Transport]) -> TelemetryBackend:
    """
    Every path that cannot use Sentry ends in NoOpBackend, so a bad setting never reaches another destination.
    :param config:
    :param transport:
    :return:
    """
    requested = config.TELEMETRY_BACKEND or BACKEND_SENTRY
    if requested == BACKEND_NOOP:
        return NoOpBackend()
    if requested != BACKEND_SENTRY:
        # Do not echo the value: a misplaced secret must not reach the logs.
        logger.warning("Telemetry disabled: TELEMETRY_BACKEND must be %s or %s", BACKEND_SENTRY, BACKEND_NOOP)
        return NoOpBackend()
    backend = SentryBackend(config, transport)
    return backend if backend.start() else NoOpBackend()


def select_telemetry_backend(config: Configuration = settings, transport: Optional[Transport] = None) -> TelemetryBackend:
    """
    Select the process's backend on the first call. Later calls return it unchanged.
    :param config:
    :param transport: Test-only override; production uses the SDK HTTP transport.
    :return:
    """
    global _selected_backend
    if _selected_backend is None:
        _selected_backend = _resolve_backend(config, transport)
    return _selected_backend


def get_telemetry_backend() -> TelemetryBackend:
    """
    :return: The selected backend, or a NoOpBackend before selection
    """
    return _selected_backend if _selected_backend is not None else _UNSELECTED_BACKEND


def capture_request_failure(request: Request, exc: Exception) -> None:
    """
    Report an unexpected exception or 5xx response through the selected backend.
    :param request:
    :param exc:
    :return:
    """
    get_telemetry_backend().capture_request_failure(request, exc)


def capture_diagnostic_event() -> Optional[str]:
    """
    Send a fixed, non-sensitive message through the selected backend.
    :return: Event id, or None when nothing was sent
    """
    return get_telemetry_backend().capture_diagnostic_event()


def flush_telemetry() -> None:
    """
    Deliver the selected backend's buffered telemetry during application shutdown.
    :return:
    """
    get_telemetry_backend().flush()


def bind_http_request(request: Request) -> ContextManager[None]:
    """
    Open the selected backend's HTTP request root (inbound frontend trace continuation).
    :param request:
    :return:
    """
    return get_telemetry_backend().bind_http_request(request)
