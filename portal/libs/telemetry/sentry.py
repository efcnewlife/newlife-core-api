"""
Sentry SDK initialization.

OpenTelemetry seam: this module never configures tracing or a tracer provider. EFC-284 owns instrumentation
through portal.libs.tracing.distributed_trace and a single OpenTelemetry provider bridged to Sentry, keeping
a later Azure Monitor exporter possible.
"""

import logging
import re
from typing import Any, Optional
from uuid import UUID

import sentry_sdk
from fastapi import HTTPException, Request
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.transport import Transport

from portal.config import Configuration, settings
from portal.libs.contexts.request_context import get_request_context
from portal.libs.logger import logger
from portal.libs.telemetry.sanitizer import drop_breadcrumb, sanitize_event, sanitize_log

LOCAL_RELEASE_VERSION = "local"
# Deployed environments must carry a real build version; dev always reports "local".
_RELEASE_VERSION_PATTERNS = {"prod": re.compile(r"^\d+\.\d+\.\d+$"), "stg": re.compile(r"^[0-9a-f]{7,12}$")}
# Request state key: AuthMiddleware runs in a child task, so a ContextVar it sets is invisible to the error handlers.
_REQUEST_USER_ID_STATE = "telemetry_user_id"
_REQUEST_ID_STATE = "telemetry_request_id"
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


def init_sentry(config: Configuration = settings, transport: Optional[Transport] = None) -> bool:
    """
    Initialize the Sentry SDK once for the process.
    :param config:
    :param transport: Test-only override; production uses the SDK HTTP transport.
    :return: Whether the SDK is active
    """
    if sentry_sdk.is_initialized():
        return True
    if not config.SENTRY_ENABLED or not config.SENTRY_DSN:
        return False
    release = _resolve_release(config)
    if release is None:
        logger.warning("Sentry disabled: environment %r with version %r has no valid release", config.ENV, config.APP_VERSION)
        return False
    try:
        sentry_sdk.init(
            dsn=config.SENTRY_DSN,
            environment=config.ENV,
            release=release,
            transport=transport,
            # Errors are captured explicitly by the HTTP error handlers (capture_request_failure), never from logs.
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[AtexitIntegration(), DedupeIntegration(), LoggingIntegration(level=None, event_level=None, sentry_logs_level=logging.WARNING)],
            max_breadcrumbs=0,
            before_breadcrumb=drop_breadcrumb,
            enable_logs=True,
            before_send=sanitize_event,
            before_send_log=_before_send_log,
            before_send_metric=_drop_metric,
            auto_session_tracking=False,
            send_client_reports=False,
            # Tracing stays off; EFC-284 composes it through OpenTelemetry.
            traces_sample_rate=None,
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


def capture_diagnostic_event() -> Optional[str]:
    """
    Send a fixed, non-sensitive message to verify the SDK configuration.
    :return: Event id, or None when the SDK is inactive
    """
    return sentry_sdk.capture_message("newlife-core-api Sentry diagnostic", level="info")


def bind_request_user(request: Request, user_id: UUID) -> None:
    """
    Remember the authenticated internal user ID on the request for failure capture.
    :param request:
    :param user_id:
    :return:
    """
    setattr(request.state, _REQUEST_USER_ID_STATE, user_id)


def bind_request_id(request: Request, request_id: str) -> None:
    """
    Remember the server-generated request ID; the request ContextVar is already reset when error handlers run.
    :param request:
    :param request_id:
    :return:
    """
    setattr(request.state, _REQUEST_ID_STATE, request_id)


def _route_template(request: Request) -> Optional[str]:
    """
    Full path with the matched route's own template in place of its raw values; None before routing matched.
    The route only knows its own path, so the leading literal part (mount root path and router prefixes, which
    carry no parameters in this app) is taken from the raw path up to where the route's pattern matches.
    :param request:
    :return:
    """
    route = request.scope.get("route")
    path_regex = getattr(route, "path_regex", None)
    path_format = getattr(route, "path_format", None)
    if path_regex is None or path_format is None:
        return None
    path = request.scope["path"]
    for index, char in enumerate(path):
        if char == "/" and path_regex.match(path[index:]):
            return f"{path[:index]}{path_format}"
    return None


def capture_request_failure(request: Request, exc: Exception) -> None:
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
            user_id = getattr(request.state, _REQUEST_USER_ID_STATE, None)
            scope.set_user({"id": str(user_id)} if user_id else None)
            scope.set_tag("http.request.method", request.method)
            request_id = getattr(request.state, _REQUEST_ID_STATE, None)
            if request_id:
                scope.set_tag(REQUEST_ID_KEY, request_id)
            route_template = _route_template(request)
            if route_template:
                scope.set_transaction_name(route_template)
            scope.capture_exception(exc)
    except Exception as e:
        logger.warning("Sentry capture failed: %s", e.__class__.__name__)
