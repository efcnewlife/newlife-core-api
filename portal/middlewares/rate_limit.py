"""
Rate limit: reject a client's burst before the request context, authentication, or any other Redis or PostgreSQL work.
"""

from fastapi import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from portal.libs.depends.rate_limiters import acquire_rate_limit
from portal.libs.logger import logger
from portal.libs.telemetry import capture_exception

_CONFIG_TYPE = "default"
_LIMITED_PATH_PREFIXES = ("/admin/api/v1/", "/api/")


class RateLimitMiddleware:
    """
    Runs once per request, in the public application only, inside trusted ingress (it needs the client IP) and CORS
    (browsers must be able to read the 429). Reads the limiters lifespan attached to the application.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self._is_limited(scope) and not await self._acquire(Request(scope)):
            await JSONResponse(content={"detail": "Too Many Requests"}, status_code=429)(scope, receive, send)
            return
        await self.app(scope, receive, send)

    @staticmethod
    def _is_limited(scope: Scope) -> bool:
        return scope["type"] == "http" and scope["method"] != "OPTIONS" and scope["path"].startswith(_LIMITED_PATH_PREFIXES)

    @staticmethod
    async def _acquire(request: Request) -> bool:
        """
        :param request:
        :return: False when a window is full; True otherwise, including when the limiter itself fails
        """
        try:
            return await acquire_rate_limit(request, _CONFIG_TYPE)
        except Exception as e:
            # Fail open: limiting is protection, not a dependency of the request.
            logger.warning("Rate limiter failed, request let through: %s", e.__class__.__name__)
            capture_exception(e)
            return True
