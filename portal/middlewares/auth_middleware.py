"""
Authentication and Authorization Middleware
"""
from collections import defaultdict
from typing import Optional

from dependency_injector.wiring import inject, Provide
from fastapi import Request
from fastapi.security.http import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response, JSONResponse

from portal.config import settings
from portal.container import Container
from portal.exceptions.responses import UnauthorizedException, InvalidTokenException, ForbiddenException
from portal.handlers import AdminUserHandler, UserHandler
from portal.libs.authorization.auth_config import AuthConfig
from portal.libs.authorization.permission_checker import PermissionChecker
from portal.libs.contexts.user_context import UserContext, set_user_context, get_user_context
from portal.libs.logger import logger
from portal.providers.jwt_provider import JWTProvider
from portal.schemas.base import AccessTokenPayload
from portal.schemas.user import SUserSensitive, SUserDetail


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication and Authorization Middleware

    This middleware handles:
    - Token verification (Authentication)
    - Permission checking (Authorization)

    Both are handled in middleware, no dependency injection needed.
    """

    def __init__(self, app):
        super().__init__(app)
        self._http_bearer = HTTPBearer(auto_error=False)

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        Process request: authenticate and authorize
        :param request: FastAPI Request
        :param call_next: Next middleware/handler
        :return: Response
        """
        # Get auth_config from route metadata
        auth_config: Optional[AuthConfig] = self._get_auth_config_from_route(request)

        # If authentication is required, verify token and check permissions
        logger.debug(f"Auth config: {auth_config}")
        if auth_config:
            try:
                if auth_config.require_auth:
                    await self._authenticate(request, auth_config)

                # Check permissions if required
                if auth_config.has_permission_check():
                    await self._check_permissions(request=request, auth_config=auth_config)
            except (UnauthorizedException, InvalidTokenException, ForbiddenException) as exc:
                # Return error response
                content = defaultdict()
                headers = None
                content["detail"] = exc.detail
                if settings.is_dev:
                    content["debug_detail"] = exc.debug_detail
                    content["url"] = str(request.url)
                if exc.headers:
                    headers = exc.headers
                return JSONResponse(
                    content=content,
                    status_code=exc.status_code,
                    headers=headers
                )

        return await call_next(request)

    def _get_auth_config_from_route(self, request: Request) -> Optional[AuthConfig]:
        """
        Get auth_config from route metadata
        In FastAPI, routes are matched after middleware execution,
        so we need to manually match routes by path and method.
        :param request: FastAPI Request
        :return: AuthConfig or None
        """
        # Try to get from route if already matched (shouldn't happen in middleware, but check anyway)
        route = request.scope.get("route")
        if route:
            endpoint = getattr(route, "endpoint", None)
            if endpoint and hasattr(endpoint, "__auth_config__"):
                return getattr(endpoint, "__auth_config__")

        # Match route by path and method from app routes
        # This is necessary because routes are matched after middleware in FastAPI
        app = request.app
        path = request.url.path
        method = request.method

        # Search through all routes to find matching route
        for r in app.routes:
            # Skip non-APIRoute routes (e.g., Mount, WebSocketRoute)
            if not hasattr(r, "methods"):
                continue

            # Check if method matches
            if method not in r.methods:
                continue

            # Try to match path using path_regex (for APIRoute)
            if hasattr(r, "path_regex"):
                if r.path_regex.match(path):
                    # Route matches, get endpoint
                    endpoint = getattr(r, "endpoint", None)
                    if endpoint and hasattr(endpoint, "__auth_config__"):
                        return getattr(endpoint, "__auth_config__")

                    # Also check route's dependant (for dependency-injected endpoints)
                    dependant = getattr(r, "dependant", None)
                    if dependant:
                        call = getattr(dependant, "call", None)
                        if call and hasattr(call, "__auth_config__"):
                            return getattr(call, "__auth_config__")

            # Fallback: try exact path match (for simple routes)
            elif hasattr(r, "path") and r.path == path:
                endpoint = getattr(r, "endpoint", None)
                if endpoint and hasattr(endpoint, "__auth_config__"):
                    return getattr(endpoint, "__auth_config__")

        return None

    async def _authenticate(self, request: Request, auth_config: AuthConfig) -> None:
        """
        Authenticate request and set UserContext
        :param request: FastAPI Request
        :param auth_config: Authentication configuration
        """
        # Extract token from Authorization header
        credentials: Optional[HTTPAuthorizationCredentials] = await self._http_bearer(request)

        if not credentials:
            raise UnauthorizedException(detail="Authentication required")

        token = credentials.credentials

        # Verify token based on auth type
        if auth_config.is_admin:
            await self._verify_admin_token(request=request, token=token)
        else:
            await self._verify_user_token(request=request, token=token)

    @inject
    async def _verify_admin_token(
        self,
        request: Request,
        token: str,
        jwt_provider: JWTProvider = Provide[Container.jwt_provider],
        admin_user_handler: AdminUserHandler = Provide[Container.admin_user_handler],
    ) -> None:
        """
        Verify admin token and set UserContext
        :param request:
        :param token:
        :param jwt_provider:
        :param admin_user_handler:
        :return:
        """
        payload: AccessTokenPayload = jwt_provider.verify_token(
            token=token,
            is_admin=True
        )
        if not payload:
            raise InvalidTokenException()

        user: SUserSensitive = await admin_user_handler.get_user_detail_by_id(payload.sub)
        if not user:
            raise UnauthorizedException()
        if not user.is_active or not user.is_admin or not user.verified:
            raise UnauthorizedException()

        user_context = UserContext(
            user_id=user.id,
            phone_number=user.phone_number,
            email=user.email,
            verified=user.verified,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_admin=user.is_admin,
            last_login_at=user.last_login_at,
            first_name=user.first_name,
            last_name=user.last_name,
            gender=user.gender,
            login_admin=True,
            token=token,
            token_payload=payload.model_dump(),
            username=user.email.split("@")[0]
        )
        set_user_context(user_context)

    @inject
    async def _verify_user_token(
        self,
        request: Request,
        token: str,
        jwt_provider: JWTProvider = Provide[Container.jwt_provider],
        user_handler: UserHandler = Provide[Container.user_handler],
    ) -> None:
        """
        Verify user token and set UserContext
        :param request: FastAPI Request
        :param token: Firebase token
        """
        payload: AccessTokenPayload = jwt_provider.verify_token(
            token=token,
            is_admin=False
        )
        if not payload:
            raise InvalidTokenException()

        user: SUserDetail = await user_handler.get_user_detail_by_id(payload.sub)
        if not user:
            raise UnauthorizedException()
        if not user.is_active or not user.verified:
            raise UnauthorizedException()

        user_context = UserContext(
            user_id=user.id,
            phone_number=user.phone_number,
            email=user.email,
            verified=user.verified,
            is_active=user.is_active,
            is_superuser=user.is_superuser,
            is_admin=user.is_admin,
            last_login_at=user.last_login_at,
            first_name=user.first_name,
            last_name=user.last_name,
            gender=user.gender,
            login_admin=False,
            token=token,
            token_payload=payload.model_dump(),
            username=user.email.split("@")[0]
        )
        set_user_context(user_context)

    @inject
    async def _check_permissions(
        self,
        request: Request,
        auth_config: AuthConfig,
        permission_checker: PermissionChecker = Provide[Container.permission_checker]
    ) -> None:
        """
        Check permissions for the request
        :param request:
        :param auth_config:
        :param permission_checker:
        :return:
        """
        # Get user context (should be set by _authenticate)
        user_context = get_user_context()

        # Check if user is authenticated
        if not user_context or not user_context.user_id:
            raise UnauthorizedException(detail="Authentication required")

        # Check superuser bypass
        if auth_config.allow_superuser and user_context.is_superuser:
            return

        permission_codes = auth_config.permission_codes
        if not permission_codes:
            permission_codes = []

        if auth_config.require_all:
            # Require all permissions
            has_permission = await permission_checker.has_all_permissions(permission_codes)
            if not has_permission:
                raise ForbiddenException(
                    debug_detail=f"All permissions required: {', '.join(permission_codes)}",
                )
        else:
            # Require any permission
            has_permission = await permission_checker.has_any_permission(permission_codes)
            if not has_permission:
                raise ForbiddenException(
                    debug_detail=f"Any permission required: {', '.join(permission_codes)}",
                )
