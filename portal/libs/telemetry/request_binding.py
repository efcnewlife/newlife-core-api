"""
Backend-neutral request diagnostics, kept on request.state for failure capture.
"""

from typing import Optional
from uuid import UUID

from fastapi import Request

# Request state key: AuthMiddleware runs in a child task, so a ContextVar it sets is invisible to the error handlers.
_REQUEST_USER_ID_STATE = "telemetry_user_id"
_REQUEST_ID_STATE = "telemetry_request_id"


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


def bound_request_user_id(request: Request) -> Optional[UUID]:
    """
    :param request:
    :return: The authenticated internal user ID, if one was bound
    """
    return getattr(request.state, _REQUEST_USER_ID_STATE, None)


def bound_request_id(request: Request) -> Optional[str]:
    """
    :param request:
    :return: The server-generated request ID, if one was bound
    """
    return getattr(request.state, _REQUEST_ID_STATE, None)


def route_template(request: Request) -> Optional[str]:
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
