"""
Sentry SDK initialization.

OpenTelemetry seam: this module never configures tracing or a tracer provider. EFC-284 owns instrumentation
through portal.libs.tracing.distributed_trace and a single OpenTelemetry provider bridged to Sentry, keeping
a later Azure Monitor exporter possible.
"""

import re
from typing import Any, Optional

import sentry_sdk
from sentry_sdk.integrations.atexit import AtexitIntegration
from sentry_sdk.integrations.dedupe import DedupeIntegration
from sentry_sdk.transport import Transport

from portal.config import Configuration, settings
from portal.libs.logger import logger

LOCAL_RELEASE_VERSION = "local"
# Deployed environments must carry a real build version; dev always reports "local".
_RELEASE_VERSION_PATTERNS = {"prod": re.compile(r"^\d+\.\d+\.\d+$"), "stg": re.compile(r"^[0-9a-f]{7,12}$")}


def _drop_metric(_metric: Any, _hint: Any) -> None:
    # Custom metrics are deferred; the SDK no longer honours enable_metrics=False.
    return None


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
            # Automatic capture stays off until the error/log capture policy (EFC-281) installs its filtering.
            default_integrations=False,
            auto_enabling_integrations=False,
            integrations=[AtexitIntegration(), DedupeIntegration()],
            max_breadcrumbs=0,
            enable_logs=False,
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
