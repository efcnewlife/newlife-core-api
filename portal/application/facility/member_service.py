"""
Facility member and ministry member read services.
"""
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import (
    MemberPagesQueryCommand,
    MinistryMemberPagesQueryCommand,
    ReplaceMinistryMemberCommand,
)
from portal.application.facility.results import (
    MemberDetailResult,
    MemberPageResult,
    MinistryMemberPageResult,
)
from portal.exceptions.responses import NotFoundException
from portal.infrastructure.persistence.repositories.facility.member_repository import MemberRepository
from portal.infrastructure.persistence.repositories.facility.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class MemberService:
    """Facility member list and ministry member assignment."""

    def __init__(
        self,
        member_repository: MemberRepository,
        ministry_repository: MinistryRepository,
    ):
        self._member_repository = member_repository
        self._ministry_repository = ministry_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @distributed_trace()
    async def get_member_pages(self, command: MemberPagesQueryCommand) -> MemberPageResult:
        items, count = await self._member_repository.fetch_pages(command, self._resolved_locale_id())
        return MemberPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_member_by_id(self, user_id: UUID) -> MemberDetailResult:
        row = await self._member_repository.get_detail(user_id, self._resolved_locale_id())
        if not row:
            raise NotFoundException(detail="Member not found")
        return row

    @distributed_trace()
    async def get_ministry_member_pages(
        self,
        command: MinistryMemberPagesQueryCommand,
    ) -> MinistryMemberPageResult:
        items, count = await self._ministry_repository.fetch_member_pages(
            command,
            self._resolved_locale_id(),
        )
        return MinistryMemberPageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    @distributed_trace()
    async def replace_user_ministries(
        self,
        user_id: UUID,
        command: ReplaceMinistryMemberCommand,
    ) -> None:
        if not await self._member_repository.get_detail(user_id, self._resolved_locale_id()):
            raise NotFoundException(detail="Member not found")
        await self._ministry_repository.replace_user_ministries(
            user_id=user_id,
            ministry_ids=command.ministry_ids,
        )

    @distributed_trace()
    async def get_user_ministries(self, user_id: UUID) -> list[UUID]:
        detail = await self.get_member_by_id(user_id)
        return [item.id for item in detail.ministries]
