"""
Ministry application service.
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from portal.application.org.commands import (
    BulkIdsCommand,
    CreateMinistryCommand,
    DeleteCommand,
    PagesQueryCommand,
    ReplaceMinistryMembersCommand,
    UpdateMinistryCommand,
)
from portal.application.org.results import (
    CreateIdResult,
    MinistryDetailResult,
    MinistryListResult,
    MinistryMemberResult,
    MinistryPageResult,
)
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import ApiBaseException, BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryService:
    """Org ministry CRUD and member assignment."""

    def __init__(self, ministry_repository: MinistryRepository):
        self._repository = ministry_repository
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

    def _build_translation_payloads(
        self,
        command: CreateMinistryCommand | UpdateMinistryCommand,
    ) -> list[dict[str, Any]]:
        translation_payloads = command.translations or []
        return [
            dict(
                locale_id=item.locale_id,
                name=item.name,
                description=item.description,
                remark=item.remark,
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(self, ministry_id: UUID, translation_payloads: list) -> None:
        if not translation_payloads:
            return
        locale_ids = [item["locale_id"] for item in translation_payloads]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        rows = [dict(ministry_id=ministry_id, **item) for item in translation_payloads]
        await self._repository.upsert_translations(rows)

    @distributed_trace()
    async def get_ministry_pages(self, command: PagesQueryCommand) -> MinistryPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return MinistryPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_ministry_list(self) -> MinistryListResult:
        items = await self._repository.list_active(self._resolved_locale_id())
        return MinistryListResult(items=items)

    @distributed_trace()
    async def get_ministry_by_id(
        self,
        ministry_id: UUID,
        all_locales: bool = False,
    ) -> Optional[MinistryDetailResult]:
        return await self._repository.get_by_id(
            ministry_id,
            self._resolved_locale_id(),
            all_locales=all_locales,
        )

    @distributed_trace()
    async def create_ministry(self, command: CreateMinistryCommand) -> CreateIdResult:
        ministry_id = uuid.uuid4()
        translation_payloads = self._build_translation_payloads(command)
        if not translation_payloads:
            raise BadRequestException(detail="translations are required")
        try:
            payload = {
                "id": ministry_id,
                "owner_position_id": command.owner_position_id,
                "status": MinistryStatus.DRAFT.value,
                "has_priority_booking": command.has_priority_booking,
                "is_active": command.is_active,
                "created_by_id": self._current_user_id(),
            }
            if command.sequence is not None:
                payload["sequence"] = command.sequence
            await self._repository.insert_ministry(payload)
            await self._validate_and_upsert_translations(ministry_id, translation_payloads)
        except ApiBaseException:
            raise
        except Exception as error:
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=ministry_id)

    @distributed_trace()
    async def update_ministry(self, ministry_id: UUID, command: UpdateMinistryCommand) -> None:
        existing = await self._repository.get_by_id(ministry_id)
        if not existing:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        values = {
            "has_priority_booking": command.has_priority_booking,
            "is_active": command.is_active,
        }
        if command.owner_position_id is not None:
            values["owner_position_id"] = command.owner_position_id
        if command.sequence is not None:
            values["sequence"] = command.sequence
        affected = await self._repository.update_ministry(ministry_id, values)
        if affected == 0:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        translation_payloads = self._build_translation_payloads(command)
        if translation_payloads:
            await self._validate_and_upsert_translations(ministry_id, translation_payloads)

    @distributed_trace()
    async def delete_ministry(self, ministry_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_by_id(ministry_id):
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        if command.permanent:
            await self._repository.delete_hard(ministry_id)
        else:
            await self._repository.delete_soft(ministry_id, command.reason)

    @distributed_trace()
    async def restore_ministries(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            raise BadRequestException(detail="No ministry ids provided")
        for ministry_id in command.ids:
            await self._repository.restore_ministry(ministry_id)

    @distributed_trace()
    async def list_owned_ministries(self) -> MinistryListResult:
        user_id = self._current_user_id()
        if not user_id:
            return MinistryListResult(items=[])
        items = await self._repository.list_owned_active(user_id, self._resolved_locale_id())
        return MinistryListResult(items=items)

    @distributed_trace()
    async def list_members(self, ministry_id: UUID) -> list[MinistryMemberResult]:
        if not await self._repository.get_by_id(ministry_id):
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        return await self._repository.list_members(ministry_id)

    @staticmethod
    def validate_primary_and_secondary(members: list[MinistryMemberResult]) -> None:
        primary_count = sum(
            1 for member in members if member.member_role == MinistryMemberRole.PRIMARY.value
        )
        secondary_count = sum(
            1 for member in members if member.member_role == MinistryMemberRole.SECONDARY.value
        )
        if primary_count != 1:
            raise BadRequestException(detail="Exactly one primary ministry member is required")
        if secondary_count < 1:
            raise BadRequestException(detail="At least one secondary ministry member is required")

    @distributed_trace()
    async def replace_members(self, ministry_id: UUID, command: ReplaceMinistryMembersCommand) -> None:
        if not await self._repository.get_by_id(ministry_id):
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        member_rows = [
            dict(
                user_id=member.user_id,
                member_role=member.member_role.value,
                remark=member.remark,
            )
            for member in command.members
        ]
        await self._repository.replace_members(
            ministry_id=ministry_id,
            members=member_rows,
        )

    @distributed_trace()
    async def validate_members_for_submit(self, ministry_id: UUID) -> None:
        members = await self.list_members(ministry_id)
        self.validate_primary_and_secondary(members)
