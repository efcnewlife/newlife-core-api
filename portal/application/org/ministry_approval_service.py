"""
Ministry approval application service.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from portal.application.org.commands import (
    ApproveMinistryCommand,
    CreateMinistryCommand,
    MinistryApplicationCommand,
    PagesQueryCommand,
    RejectMinistryCommand,
    ReplaceMinistryMembersCommand,
    SubmitMinistryCommand,
)
from portal.application.org.ministry_service import MinistryService
from portal.application.org.results import CreateIdResult, MinistryApprovalResult, MinistryPageResult
from portal.domain.org.constants import MinistryApprovalStatus, MinistryStatus
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryApprovalService:
    """Ministry submission and approval workflow."""

    def __init__(
        self,
        ministry_repository: MinistryRepository,
        ministry_service: MinistryService,
    ):
        self._repository = ministry_repository
        self._ministry_service = ministry_service
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    def _current_user_id(self) -> Optional[UUID]:
        if self._user_ctx and self._user_ctx.user_id:
            return self._user_ctx.user_id
        return None

    @distributed_trace()
    async def create_application(self, command: MinistryApplicationCommand) -> CreateIdResult:
        create_result = await self._ministry_service.create_ministry(
            CreateMinistryCommand(
                owner_position_id=command.owner_position_id,
                has_priority_booking=command.has_priority_booking,
                translations=command.translations,
            )
        )
        if command.members:
            await self._ministry_service.replace_members(
                create_result.id,
                ReplaceMinistryMembersCommand(members=command.members),
            )
        await self.submit_ministry(create_result.id, SubmitMinistryCommand())
        return create_result

    @distributed_trace()
    async def submit_ministry(self, ministry_id: UUID, command: SubmitMinistryCommand) -> None:
        ministry = await self._repository.get_by_id(ministry_id)
        if not ministry:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        if ministry.status not in {MinistryStatus.DRAFT.value, MinistryStatus.REJECTED.value}:
            raise BadRequestException(detail="Ministry cannot be submitted in its current status")
        if not ministry.owner_position_id:
            raise BadRequestException(detail="owner_position_id is required before submit")
        await self._ministry_service.validate_members_for_submit(ministry_id)

        now = datetime.now(timezone.utc)
        user_id = self._current_user_id()
        await self._repository.update_ministry(
            ministry_id,
            dict(
                status=MinistryStatus.PENDING_APPROVAL.value,
                submitted_at=now,
                submitted_by_id=user_id,
                rejected_at=None,
                rejected_by_id=None,
                rejection_reason=None,
            ),
        )
        await self._repository.insert_approval(
            dict(
                id=uuid.uuid4(),
                ministry_id=ministry_id,
                owner_position_id=ministry.owner_position_id,
                status=MinistryApprovalStatus.PENDING.value,
                requested_by_id=user_id,
            )
        )

    @distributed_trace()
    async def approve_ministry(self, ministry_id: UUID, command: ApproveMinistryCommand) -> None:
        ministry = await self._repository.get_by_id(ministry_id)
        if not ministry:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        if ministry.status != MinistryStatus.PENDING_APPROVAL.value:
            raise BadRequestException(detail="Ministry is not pending approval")

        now = datetime.now(timezone.utc)
        user_id = self._current_user_id()
        await self._repository.update_ministry(
            ministry_id,
            dict(
                status=MinistryStatus.ACTIVE.value,
                is_active=True,
                approved_at=now,
                approved_by_id=user_id,
            ),
        )
        await self._repository.update_approval(
            ministry_id=ministry_id,
            status=MinistryApprovalStatus.APPROVED.value,
            resolved_by_id=user_id,
            decided_at=now,
            comment=command.comment,
        )

    @distributed_trace()
    async def reject_ministry(self, ministry_id: UUID, command: RejectMinistryCommand) -> None:
        ministry = await self._repository.get_by_id(ministry_id)
        if not ministry:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        if ministry.status != MinistryStatus.PENDING_APPROVAL.value:
            raise BadRequestException(detail="Ministry is not pending approval")

        now = datetime.now(timezone.utc)
        user_id = self._current_user_id()
        await self._repository.update_ministry(
            ministry_id,
            dict(
                status=MinistryStatus.REJECTED.value,
                rejected_at=now,
                rejected_by_id=user_id,
                rejection_reason=command.rejection_reason,
            ),
        )
        await self._repository.update_approval(
            ministry_id=ministry_id,
            status=MinistryApprovalStatus.REJECTED.value,
            resolved_by_id=user_id,
            decided_at=now,
            comment=command.comment or command.rejection_reason,
        )

    @distributed_trace()
    async def list_pending_approvals(self, command: PagesQueryCommand) -> MinistryPageResult:
        items, count = await self._repository.fetch_approval_pages(command, self._resolved_locale_id())
        return MinistryPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def list_pending_approval_requests(self, command: PagesQueryCommand) -> list[MinistryApprovalResult]:
        items, _count = await self._repository.fetch_approval_request_pages(command)
        return items
