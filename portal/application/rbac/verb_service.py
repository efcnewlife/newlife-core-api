"""
Verb list application service.
"""
from typing import Optional
from uuid import UUID

from portal.application.rbac.results import VerbListResult
from portal.domain.rbac.ports import VerbListCachePort, VerbRepositoryPort
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.tracing.distributed_trace import distributed_trace


class VerbService:
    """Load localized verb list with Redis caching."""

    def __init__(
        self,
        verb_repository: VerbRepositoryPort,
        verb_list_cache: VerbListCachePort,
    ):
        self._verb_repository = verb_repository
        self._verb_list_cache = verb_list_cache
        self._req_ctx: Optional[RequestContext] = get_request_context()

    @distributed_trace()
    async def get_verb_list(self) -> VerbListResult:
        """
        Return verbs for the resolved request locale.
        :return:
        """
        if not (self._req_ctx and self._req_ctx.resolved_locale_id):
            return VerbListResult(items=[])
        locale_id: UUID = self._req_ctx.resolved_locale_id
        cached = await self._verb_list_cache.get(locale_id)
        if cached is not None:
            return VerbListResult(items=cached)
        verbs = await self._verb_repository.list_active_by_locale(locale_id)
        if verbs:
            await self._verb_list_cache.set(locale_id, verbs)
        return VerbListResult(items=verbs)
