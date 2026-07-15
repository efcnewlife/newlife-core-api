"""
Microsoft Graph API facade for app-only directory reads (beta endpoint).
"""
from collections.abc import AsyncIterator, Callable
from typing import Optional

from portal.providers.ms_graph.models import GraphUserRecord
from portal.providers.ms_graph.users import MSGraphUsers

__all__ = [
    "GraphUserRecord",
    "MicrosoftGraphProvider",
]


class MicrosoftGraphProvider:
    """Fetch users from Microsoft Graph using the SDK-backed MSGraphUsers client."""

    def __init__(
        self,
        users_factory: Callable[[], MSGraphUsers] = MSGraphUsers,
    ) -> None:
        self._users_factory = users_factory

    def is_configured(self) -> bool:
        return self._users_factory().is_configured()

    async def list_users(
        self,
        *,
        filter_expr: str,
        select_fields: Optional[list[str]] = None,
        page_size: int = 999,
    ) -> AsyncIterator[GraphUserRecord]:
        """
        Yield users from Graph with pagination via odata_next_link.
        """
        users = self._users_factory()
        async for record in users.list_users(
            filter_expr=filter_expr,
            select_fields=select_fields,
            page_size=page_size,
        ):
            yield record
