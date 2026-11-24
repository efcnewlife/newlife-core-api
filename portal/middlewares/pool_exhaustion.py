"""
Pool exhaustion: answer 503 with Retry-After when PostgreSQL or Redis cannot hand out a connection in time.
"""

from typing import Optional

from asyncpg import TooManyConnectionsError
from fastapi import Request
from redis.exceptions import MaxConnectionsError
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from portal.libs.database.aio_pg import PoolAcquireTimeoutError
from portal.libs.telemetry import capture_request_failure

RETRY_AFTER_SECONDS = 5
_POOL_EXHAUSTED_ERRORS = (PoolAcquireTimeoutError, TooManyConnectionsError, MaxConnectionsError)


def is_pool_exhausted(exc: Optional[BaseException]) -> bool:
    """
    :param exc:
    :return: Whether the error, or one it was raised from or while handling, is an exhausted connection pool
    """
    while exc is not None:
        if isinstance(exc, _POOL_EXHAUSTED_ERRORS):
            return True
        exc = exc.__cause__ or exc.__context__
    return False


def pool_exhausted_response() -> JSONResponse:
    return JSONResponse(content={"detail": "Service Unavailable"}, status_code=503, headers={"Retry-After": str(RETRY_AFTER_SECONDS)})


class PoolExhaustionMiddleware:
    """
    Runs inside CORS in every application, because exception handlers do not see errors from middlewares and the 500
    handler answers outside CORS. CoreRequestMiddleware, further in, has already rolled the session back.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            response_started = response_started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            if response_started or not is_pool_exhausted(exc):
                raise
            capture_request_failure(Request(scope), exc)
            await pool_exhausted_response()(scope, receive, send)
