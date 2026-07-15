"""
Ministry application service.
"""
import uuid
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
from portal.application.org.ministry_schedule import build_schedule_payloads, validate_ministry_schedules
from portal.application.org.results import (
    CreateIdResult,
    MinistryDetailResult,
    MinistryListResult,
    MinistryMemberResult,
    MinistryPageResult,
)
from portal.application.org.target_audience_validation import validate_target_audience_ids
from portal.domain.org.catalog_codes import MINISTRY_TYPE_INTERNAL
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import ApiBaseException, BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.repositories.org.ministry_type_repository import MinistryTypeRepository
from portal.infrastructure.persistence.repositories.org.target_audience_repository import TargetAudienceRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class MinistryService:
    """Org ministry CRUD and member assignment."""

    def __init__(
        self,
        ministry_repository: MinistryRepository,
        ministry_type_repository: MinistryTypeRepository,
        target_audience_repository: TargetAudienceRepository,
    ):
        self._repository = ministry_repository
        self._ministry_type_repository = ministry_type_repository
        self._target_audience_repository = target_audience_repository
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
                schedule_note=item.schedule_note,
            )
            for item in translation_payloads
        ]

    async def _resolve_ministry_type_id(self, ministry_type_id: Optional[UUID]) -> UUID:
        if ministry_type_id:
            ministry_type = await self._ministry_type_repository.get_active_by_id(ministry_type_id)
            if not ministry_type:
                raise BadRequestException(detail="Invalid or inactive ministry_type_id")
            return ministry_type_id
        default_id = await self._ministry_type_repository.get_id_by_code(MINISTRY_TYPE_INTERNAL)
        if not default_id:
            raise BadRequestException(detail="Default ministry type is not seeded")
        return default_id

    async def _validate_target_audiences(self, audience_ids: list[UUID]) -> None:
        if not audience_ids:
            return
        active_audiences = await self._target_audience_repository.fetch_active_by_ids(audience_ids)
        validate_target_audience_ids(audience_ids, active_audiences)

    async def _validate_and_upsert_translations(self, ministry_id: UUID, translation_payloads: list) -> None:
        if not translation_payloads:
            return
        locale_ids = [item["locale_id"] for item in translation_payloads]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        rows = [dict(ministry_id=ministry_id, **item) for item in translation_payloads]
        await self._repository.upsert_translations(rows)

    async def _upsert_schedules(self, ministry_id: UUID, schedules) -> None:
        if schedules is None:
            return
        validate_ministry_schedules(schedules)
        await self._repository.upsert_schedules(ministry_id, build_schedule_payloads(schedules))

    async def _upsert_target_audiences(self, ministry_id: UUID, audience_ids: Optional[list[UUID]]) -> None:
        if audience_ids is None:
            return
        await self._validate_target_audiences(audience_ids)
        await self._repository.upsert_target_audiences(ministry_id, audience_ids)

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
        ministry_type_id = await self._resolve_ministry_type_id(command.ministry_type_id)
        await self._validate_target_audiences(command.target_audience_ids)
        validate_ministry_schedules(command.schedules)
        try:
            payload = {
                "id": ministry_id,
                "owner_position_id": command.owner_position_id,
                "ministry_type_id": ministry_type_id,
                "status": MinistryStatus.DRAFT.value,
                "has_priority_booking": command.has_priority_booking,
                "is_active": command.is_active,
                "created_by_id": self._current_user_id(),
            }
            if command.sequence is not None:
                payload["sequence"] = command.sequence
            await self._repository.insert_ministry(payload)
            await self._validate_and_upsert_translations(ministry_id, translation_payloads)
            await self._repository.upsert_schedules(ministry_id, build_schedule_payloads(command.schedules))
            await self._repository.upsert_target_audiences(ministry_id, command.target_audience_ids)
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
        if command.ministry_type_id is not None:
            values["ministry_type_id"] = await self._resolve_ministry_type_id(command.ministry_type_id)
        if command.sequence is not None:
            values["sequence"] = command.sequence
        affected = await self._repository.update_ministry(ministry_id, values)
        if affected == 0:
            raise NotFoundException(detail=f"Ministry {ministry_id} not found")
        translation_payloads = self._build_translation_payloads(command)
        if translation_payloads:
            await self._validate_and_upsert_translations(ministry_id, translation_payloads)
        await self._upsert_schedules(ministry_id, command.schedules)
        await self._upsert_target_audiences(ministry_id, command.target_audience_ids)

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
                contact_email=member.contact_email,
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
