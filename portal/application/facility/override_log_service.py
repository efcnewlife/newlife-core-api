"""
Facility booking override audit log read service.
"""
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import OverrideLogPagesQueryCommand
from portal.application.facility.results import OverrideLogPageResult
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.tracing.distributed_trace import distributed_trace


class OverrideLogService:
    """Read-only override audit log."""

    def __init__(self, override_log_repository: OverrideLogRepository):
        self._repository = override_log_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @distributed_trace()
    async def get_override_log_pages(self, command: OverrideLogPagesQueryCommand) -> OverrideLogPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return OverrideLogPageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )
