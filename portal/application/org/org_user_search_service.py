"""
Member-facing auth user search for ministry steward picker.
"""

from typing import Optional
from uuid import UUID

from portal.application.org.commands import OrgUserSearchCommand
from portal.application.org.results import OrgUserSearchListResult
from portal.exceptions.responses import BadRequestException
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace

MIN_QUERY_LENGTH = 2
MAX_RESULTS = 20


class OrgUserSearchService:
    """Search active auth users by email or display name."""

    def __init__(self, user_repository: UserRepository):
        self._repository = user_repository
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _current_user_id(self) -> Optional[UUID]:
        if self._user_ctx and self._user_ctx.user_id:
            return self._user_ctx.user_id
        return None

    @distributed_trace()
    async def search_users(self, command: OrgUserSearchCommand) -> OrgUserSearchListResult:
        keyword = command.q.strip()
        if len(keyword) < MIN_QUERY_LENGTH:
            raise BadRequestException(detail=f"Query must be at least {MIN_QUERY_LENGTH} characters")
        rows = await self._repository.search_active_users(keyword=keyword, exclude_user_id=self._current_user_id(), limit=MAX_RESULTS)
        return OrgUserSearchListResult(items=rows)
