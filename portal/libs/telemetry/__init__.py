"""
Telemetry backend selection and backend-neutral entry points.
"""

from portal.libs.telemetry.backend import NOOP_SPAN, NoOpBackend, TelemetryBackend, TraceSpan
from portal.libs.telemetry.request_binding import bind_request_id, bind_request_user
from portal.libs.telemetry.selection import capture_diagnostic_event, capture_request_failure, flush_telemetry, get_telemetry_backend, select_telemetry_backend
from portal.libs.telemetry.sentry import SentryBackend

__all__ = [
    "NOOP_SPAN",
    "NoOpBackend",
    "SentryBackend",
    "TelemetryBackend",
    "TraceSpan",
    "bind_request_id",
    "bind_request_user",
    "capture_diagnostic_event",
    "capture_request_failure",
    "flush_telemetry",
    "get_telemetry_backend",
    "select_telemetry_backend",
]
