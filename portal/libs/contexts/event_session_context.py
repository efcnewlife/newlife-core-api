"""
Event-scoped database session context.

Used when running event handlers (e.g. background tasks) so they get a dedicated
session that is committed/rolled back and closed after the handler runs,
instead of relying on the request-scoped session.
"""

from contextvars import ContextVar, Token
from typing import Optional

from portal.libs.database import Session


_event_session_ctx: ContextVar[Optional[Session]] = ContextVar("event_session_ctx", default=None)


def set_event_session(session: Session) -> Token:
    return _event_session_ctx.set(session)


def get_event_session() -> Optional[Session]:
    return _event_session_ctx.get()


def reset_event_session(token: Token) -> None:
    _event_session_ctx.reset(token)
