"""
Request-scoped database session context helpers.
"""

from contextvars import ContextVar, Token
from typing import Optional

from portal.libs.database import Session


_request_session_ctx: ContextVar[Optional[Session]] = ContextVar("request_session_ctx", default=None)


def set_request_session(session: Session) -> Token:
    return _request_session_ctx.set(session)


def get_request_session() -> Optional[Session]:
    return _request_session_ctx.get()


def reset_request_session(token) -> None:
    _request_session_ctx.reset(token)


