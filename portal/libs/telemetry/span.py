"""
Vendor-neutral TraceSpan adapters used by TelemetryBackend.start_span.
"""

from sentry_sdk.tracing import Span

from portal.libs.telemetry.backend import SpanAttributeValue
from portal.libs.telemetry.sanitizer import sanitize_span_attribute


class SentryTraceSpan:
    """
    Wraps the Sentry-native span created for one decorated operation. No finish or child-span API.
    """

    __slots__ = ("_span",)

    def __init__(self, span: Span) -> None:
        self._span = span

    def set_attribute(self, key: str, value: SpanAttributeValue) -> None:
        try:
            sanitized = sanitize_span_attribute(key, value)
            if sanitized is None:
                return
            attribute_key, attribute_value = sanitized
            self._span.set_data(attribute_key, attribute_value)
        except Exception:
            return None
