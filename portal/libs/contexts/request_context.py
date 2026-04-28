"""
Request Context (per-request)
"""
from contextvars import ContextVar, Token
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.schemas.base import HeaderInfo


class RequestContext(BaseModel):
    """Per-request HTTP information"""
    request_id: Optional[str] = None
    ip: Optional[str] = None
    client_ip: Optional[str] = None
    method: Optional[str] = None
    host: Optional[str] = None
    url: Optional[str] = None
    path: Optional[str] = None
    headers: HeaderInfo
    locale_candidates: list[str] = Field(default_factory=list)
    resolved_locale_code: Optional[str] = None
    resolved_locale_id: Optional[UUID] = None


request_context_var: ContextVar[RequestContext] = ContextVar("RequestContext")


def set_request_context(context: RequestContext) -> Token:
    """
    Set the request context for current request.
    """
    return request_context_var.set(context)


def get_request_context() -> Optional[RequestContext]:
    """
    Get current request's request context.
    """
    try:
        return request_context_var.get()
    except LookupError:
        return None


def get_resolved_locale_id() -> Optional[UUID]:
    """
    Return resolved locale id for the current request, or None if context is not set
    (e.g. background task) or locale is unresolved.
    """
    try:
        ctx = get_request_context()
    except LookupError:
        return None
    return ctx.resolved_locale_id


def reset_request_context(token) -> None:
    """
    Reset the request context for current request.
    :param token:
    :return:
    """
    request_context_var.reset(token)
