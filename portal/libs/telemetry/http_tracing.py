"""
HTTP request root spans: continue supported frontend trace headers without a second SDK init.
"""

import sys
from collections.abc import Iterator
from contextlib import contextmanager

import sentry_sdk
from fastapi import Request

from portal.libs.logger import logger
from portal.libs.telemetry.request_binding import route_template
from portal.libs.telemetry.trace_context import http_trace_active, reset_http_trace_active, set_http_trace_active


def _refresh_transaction_name(request: Request) -> None:
    template = route_template(request)
    if not template:
        return
    span = sentry_sdk.get_current_span()
    if span is None:
        return
    transaction = span.containing_transaction
    if transaction is None:
        return
    try:
        transaction.name = template
    except Exception:
        return


@contextmanager
def sentry_bind_http_request(request: Request) -> Iterator[None]:
    """
    Continue inbound sentry-trace/baggage when present and open one http.server transaction for the request.
    :param request:
    :return:
    """
    if not sentry_sdk.is_initialized():
        yield None
        return

    if http_trace_active():
        # Public middleware already opened the root for a mounted admin/api request.
        try:
            yield None
        finally:
            _refresh_transaction_name(request)
        return

    native_cm = None
    transaction = None
    http_token = set_http_trace_active(True)
    try:
        headers = {key: value for key, value in request.headers.items()}
        transaction = sentry_sdk.continue_trace(headers, op="http.server", name=request.url.path)
        native_cm = sentry_sdk.start_transaction(transaction)
        native_cm.__enter__()
    except Exception as e:
        logger.warning("Sentry request trace setup failed: %s", e.__class__.__name__)
        reset_http_trace_active(http_token)
        yield None
        return

    caught: BaseException | None = None
    try:
        yield None
    except BaseException as exc:
        caught = exc
        try:
            transaction.set_status("internal_error")
        except Exception:
            pass
        raise
    else:
        try:
            transaction.set_status("ok")
        except Exception:
            pass
    finally:
        _refresh_transaction_name(request)
        try:
            if caught is not None:
                native_cm.__exit__(*sys.exc_info())
            else:
                native_cm.__exit__(None, None, None)
        except Exception as e:
            logger.warning("Sentry request trace finish failed: %s", e.__class__.__name__)
        reset_http_trace_active(http_token)
