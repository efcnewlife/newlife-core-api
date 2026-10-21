"""
Request-session adapter for TransactionHooksPort.
"""

from typing import Awaitable, Callable

from portal.libs.database import Session


class SessionTransactionHooks:
    """Register after-commit callbacks on the request-scoped Session."""

    def __init__(self, session: Session):
        self._session = session

    def after_commit(self, callback: Callable[[], Awaitable[None]]) -> None:
        self._session.add_after_commit(callback)
