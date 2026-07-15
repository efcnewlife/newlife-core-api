"""
Ministry catalog list application service.
"""
from typing import Optional
from uuid import UUID

from portal.application.org.results import MinistryTypeListResult, TargetAudienceListResult
from portal.infrastructure.persistence.repositories.org.ministry_type_repository import MinistryTypeRepository
from portal.infrastructure.persistence.repositories.org.target_audience_repository import TargetAudienceRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryCatalogService:
    """Read-only ministry type and target audience catalogs."""

    def __init__(
        self,
        ministry_type_repository: MinistryTypeRepository,
        target_audience_repository: TargetAudienceRepository,
    ):
        self._ministry_type_repository = ministry_type_repository
        self._target_audience_repository = target_audience_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @distributed_trace()
    async def list_ministry_types(self) -> MinistryTypeListResult:
        items = await self._ministry_type_repository.list_active(self._resolved_locale_id())
        return MinistryTypeListResult(items=items)

    @distributed_trace()
    async def list_target_audiences(self) -> TargetAudienceListResult:
        items = await self._target_audience_repository.list_active(self._resolved_locale_id())
        return TargetAudienceListResult(items=items)
