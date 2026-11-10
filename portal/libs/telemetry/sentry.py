"""
Sentry telemetry backend: owns SDK init, capture, and span creation for the Sentry destination.

HTTP request roots live in portal.libs.telemetry.http_tracing and are reached only through this backend.
"""

import logging
import re
import sys
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any, ContextManager, Optional

import sentry_sdk
from fastapi import HTTPException, Request
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from portal.config import Configuration, settings
from portal.libs.contexts.request_context import get_request_context
from portal.libs.logger import logger
from portal.libs.telemetry.backend import NOOP_SPAN, TraceSpan
from portal.libs.telemetry.http_tracing import sentry_bind_http_request
from portal.libs.telemetry.request_binding import bound_request_id, bound_request_user_id, route_template
from portal.libs.telemetry.sanitizer import drop_breadcrumb, sanitize_event, sanitize_log, sanitize_transaction
from portal.libs.telemetry.span import SentryTraceSpan
from portal.libs.telemetry.trace_context import push_span_depth, reset_span_depth, should_open_child_span


def _exit_context(context: Any, caught: BaseException | None = None) -> None:
    try:
        if caught is not None:
            context.__exit__(*sys.exc_info())
        else:
            context.__exit__(None, None, None)
    except Exception:
        return


LOCAL_RELEASE_VERSION = "local"
# Deployed environments must carry a real build version; dev always reports "local".
_RELEASE_VERSION_PATTERNS = {"prod": re.compile(r"^\d+\.\d+\.\d+$"), "stg": re.compile(r"^[0-9a-f]{7,12}$")}
# Shared by error events (tag) and logs (attribute) so one request's logs can be found from its error.
REQUEST_ID_KEY = "request_id"
# Mounted apps re-raise into the public app's handler; this marks a failure already reported once.
_CAPTURED_FLAG = "__telemetry_captured__"


def _drop_metric(_metric: Any, _hint: Any) -> None:
    # Custom metrics are deferred; the SDK no longer honours enable_metrics=False.
    return None


def _before_send_log(log: dict[str, Any], hint: Any) -> Optional[dict[str, Any]]:
    log = sanitize_log(log, hint)
    request_context = get_request_context()
    if request_context is not None and request_context.request_id:
        log["attributes"][REQUEST_ID_KEY] = request_context.request_id
    return log


def _resolve_release(config: Configuration) -> Optional[str]:
    """
    Build `<app>@<version>`, or None when the environment/version pair is not trustworthy.
    :param config:
    :return:
    """
    if config.ENV == "dev":
        return f"{config.APP_NAME}@{LOCAL_RELEASE_VERSION}"
    pattern = _RELEASE_VERSION_PATTERNS.get(config.ENV)
    if pattern is None or not pattern.fullmatch(config.APP_VERSION):
        return None
    return f"{config.APP_NAME}@{config.APP_VERSION}"


class SentryBackend:
    """
    Sentry owns remote errors and sanitized logs. Its LoggingIntegration is the only remote log handler.
    """

    def __init__(self, config: Configuration = settings, transport: Optional[Transport] = None) -> None:
        """
        :param config:
        :param transport: Test-only override; production uses the SDK HTTP transport.
        """
        self._config = config
        self._transport = transport

    def start(self) -> bool:
        """
        Initialize the Sentry SDK once for the process.
        :return: Whether the SDK is active
        """
        if sentry_sdk.is_initialized():
            return True
        if not self._config.SENTRY_ENABLED or not self._config.SENTRY_DSN:
            return False
        release = _resolve_release(self._config)
        if release is None:
            logger.warning("Sentry disabled: environment %r with version %r has no valid release", self._config.ENV, self._config.APP_VERSION)
            return False
        try:
            sentry_sdk.init(
                dsn=self._config.SENTRY_DSN,
                environment=self._config.ENV,
                release=release,
                transport=self._transport,
                # Errors are captured explicitly by the HTTP error handlers (capture_request_failure), never from logs.
                default_integrations=False,
                auto_enabling_integrations=False,
                integrations=[AtexitIntegration(), DedupeIntegration(), LoggingIntegration(level=None, event_level=None, sentry_logs_level=logging.WARNING)],
                max_breadcrumbs=0,
                before_breadcrumb=drop_breadcrumb,
                enable_logs=True,
                before_send=sanitize_event,
                before_send_transaction=sanitize_transaction,
                before_send_log=_before_send_log,
                before_send_metric=_drop_metric,
                auto_session_tracking=False,
                send_client_reports=False,
                # None keeps tracing off. Set SENTRY_TRACES_SAMPLE_RATE to export Sentry-native spans.
                traces_sample_rate=self._config.SENTRY_TRACES_SAMPLE_RATE,
                # send_default_pii and data_collection stay unset: the SDK then resolves to no PII and keeps its
                # default EventScrubber, which an explicit data_collection would disable.
                include_local_variables=False,
                max_request_body_size="never",
            )
        except Exception as e:
            # Telemetry must never block startup. Log only the type: SDK messages can echo the DSN.
            logger.warning("Sentry disabled: SDK initialization failed: %s", e.__class__.__name__)
            return False
        return sentry_sdk.is_initialized()

    def flush(self) -> None:
        """
        Deliver buffered events and logs. The client stays open: AtexitIntegration closes it when the process exits.
        :return:
        """
        try:
            sentry_sdk.flush()
        except Exception as e:
            logger.warning("Sentry flush failed: %s", e.__class__.__name__)

    def capture_request_failure(self, request: Request, exc: Exception) -> None:
        """
        Report an unexpected exception or 5xx response once, with only the route, method, and internal user ID.
        Never raises: telemetry must not change the response.
        :param request:
        :param exc:
        :return:
        """
        if not sentry_sdk.is_initialized() or getattr(exc, _CAPTURED_FLAG, False):
            return
        if isinstance(exc, HTTPException) and exc.status_code < 500:
            return
        try:
            # Flag first: if capture itself fails, the outer app's handler must not retry it.
            setattr(exc, _CAPTURED_FLAG, True)
            with sentry_sdk.new_scope() as scope:
                user_id = bound_request_user_id(request)
                scope.set_user({"id": str(user_id)} if user_id else None)
                scope.set_tag("http.request.method", request.method)
                request_id = bound_request_id(request)
                if request_id:
                    scope.set_tag(REQUEST_ID_KEY, request_id)
                template = route_template(request)
                if template:
                    scope.set_transaction_name(template)
                scope.capture_exception(exc)
        except Exception as e:
            logger.warning("Sentry capture failed: %s", e.__class__.__name__)

    def capture_diagnostic_event(self) -> Optional[str]:
        """
        Send a fixed, non-sensitive message to verify the SDK configuration.
        :return: Event id, or None when the SDK is inactive
        """
        try:
            return sentry_sdk.capture_message("newlife-core-api Sentry diagnostic", level="info")
        except Exception as e:
            logger.warning("Sentry capture failed: %s", e.__class__.__name__)
            return None

    def bind_http_request(self, request: Request) -> ContextManager[None]:
        """
        Continue inbound frontend trace headers and open one http.server transaction for the request.
        :param request:
        :return:
        """
        return sentry_bind_http_request(request)

    @contextmanager
    def start_span(self, name: str) -> Iterator[TraceSpan]:
        """
        Open a child span under the active request/parent, or an isolated transaction root for standalone work.
        :param name: Stable operation name
        :return:
        """
        if not sentry_sdk.is_initialized():
            yield NOOP_SPAN
            return

        # Decide before pushing depth so concurrent tasks do not inherit a sibling's Sentry span by mistake.
        open_child = should_open_child_span()
        depth_token = push_span_depth()
        isolation_cm: Any = nullcontext()
        native_cm = None
        native = None
        try:
            if open_child:
                native_cm = sentry_sdk.start_span(op="function", name=name)
            else:
                isolation_cm = sentry_sdk.isolation_scope()
                isolation_cm.__enter__()
                native_cm = sentry_sdk.start_transaction(name=name, op="function")
            native = native_cm.__enter__()
        except Exception as e:
            logger.warning("Sentry span setup failed: %s", e.__class__.__name__)
            _exit_context(isolation_cm)
            reset_span_depth(depth_token)
            yield NOOP_SPAN
            return

        caught: BaseException | None = None
        try:
            yield SentryTraceSpan(native)
        except BaseException as exc:
            caught = exc
            try:
                native.set_status("internal_error")
            except Exception:
                pass
            raise
        else:
            try:
                native.set_status("ok")
            except Exception:
                pass
        finally:
            try:
                if caught is not None:
                    native_cm.__exit__(*sys.exc_info())
                else:
                    native_cm.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Sentry span finish failed: %s", e.__class__.__name__)
            _exit_context(isolation_cm, caught)
            reset_span_depth(depth_token)
