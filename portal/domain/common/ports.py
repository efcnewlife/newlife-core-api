"""
Cross-context ports.
"""

from typing import Awaitable, Callable, Protocol


class TransactionHooksPort(Protocol):
    """Defer side effects until the current unit of work commits; discarded on rollback."""

    def after_commit(self, callback: Callable[[], Awaitable[None]]) -> None: ...
