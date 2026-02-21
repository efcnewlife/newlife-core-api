"""
Request Context (per-request)
"""
from contextvars import ContextVar, Token
from typing import Optional

from pydantic import BaseModel


class RequestContext(BaseModel):
    """Per-request HTTP information"""

    ip: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None
    method: Optional[str] = None
    host: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    request_id: Optional[str] = None


request_context_var: ContextVar[RequestContext] = ContextVar("RequestContext")


def set_request_context(context: RequestContext) -> Token:
    """
    Set the request context for current request.
    """
    return request_context_var.set(context)


def get_request_context() -> RequestContext:
    """
    Get current request's request context.
    """
    return request_context_var.get()


def reset_request_context(token) -> None:
    """
    Reset the request context for current request.
    :param token:
    :return:
    """
    request_context_var.reset(token)
