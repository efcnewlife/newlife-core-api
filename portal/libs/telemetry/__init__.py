"""
Telemetry SDK wiring.
"""

from portal.libs.telemetry.sentry import capture_diagnostic_event, init_sentry

__all__ = ["capture_diagnostic_event", "init_sentry"]
