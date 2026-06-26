"""
Position application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.application.org.commands import (
    AssignPositionCommand,
    BulkIdsCommand,
    CreatePositionCommand,
    DeleteCommand,
    PagesQueryCommand,
    PositionTranslationCommand,
    UpdatePositionCommand,
)
from portal.application.org.results import (
    AssignablePositionResult,
    CreateIdResult,
    PositionDetailResult,
    PositionPageResult,
)
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.tracing.distributed_trace import distributed_trace


class PositionService:
    """Church leadership position use cases."""

    def __init__(self, position_repository: PositionRepository):
        self._repository = position_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    def _build_translation_payloads(
        self,
        command: CreatePositionCommand | UpdatePositionCommand,
    ) -> list[dict[str, Any]]:
        translation_payloads = command.translations or []
        team = command.team.value
        office = command.office.value
        return [
            dict(
                locale_id=item.locale_id,
                team=team,
                office=office,
                name=item.name,
                description=item.description,
                remark=item.remark,
            )
            for item in translation_payloads
        ]

    async def _validate_and_upsert_translations(self, position_id: UUID, translation_payloads: list) -> None:
        if not translation_payloads:
            return
        locale_ids = [item["locale_id"] for item in translation_payloads]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        rows = [dict(position_id=position_id, **item) for item in translation_payloads]
        await self._repository.upsert_translations(rows)

    @distributed_trace()
    async def get_position_pages(self, command: PagesQueryCommand) -> PositionPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return PositionPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_position_by_id(
        self,
        position_id: UUID,
        all_locales: bool = False,
    ) -> Optional[PositionDetailResult]:
        return await self._repository.get_by_id(
            position_id,
            self._resolved_locale_id(),
            all_locales=all_locales,
        )

    @distributed_trace()
    async def list_assignable(self) -> list[AssignablePositionResult]:
        return await self._repository.list_assignable(self._resolved_locale_id())

    @distributed_trace()
    async def create_position(self, command: CreatePositionCommand) -> CreateIdResult:
        position_id = uuid.uuid4()
        translation_payloads = self._build_translation_payloads(command)
        if not translation_payloads:
            raise BadRequestException(detail="translations are required")
        try:
            payload = {
                "id": position_id,
                "code": command.code,
                "can_own_ministry": command.can_own_ministry,
                "is_active": command.is_active,
            }
            if command.sequence is not None:
                payload["sequence"] = command.sequence
            await self._repository.insert_position(payload)
            await self._validate_and_upsert_translations(position_id, translation_payloads)
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Position code already exists", debug_detail=str(error))
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=position_id)

    @distributed_trace()
    async def update_position(self, position_id: UUID, command: UpdatePositionCommand) -> None:
        if not await self._repository.get_by_id(position_id):
            raise NotFoundException(detail=f"Position {position_id} not found")
        values = {
            "can_own_ministry": command.can_own_ministry,
            "is_active": command.is_active,
        }
        if command.sequence is not None:
            values["sequence"] = command.sequence
        affected = await self._repository.update_position(position_id, values)
        if affected == 0:
            raise NotFoundException(detail=f"Position {position_id} not found")
        translation_payloads = self._build_translation_payloads(command)
        if translation_payloads:
            await self._validate_and_upsert_translations(position_id, translation_payloads)

    @distributed_trace()
    async def delete_position(self, position_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_by_id(position_id):
            raise NotFoundException(detail=f"Position {position_id} not found")
        if command.permanent:
            await self._repository.delete_hard(position_id)
        else:
            await self._repository.delete_soft(position_id, command.reason)

    @distributed_trace()
    async def restore_positions(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            raise BadRequestException(detail="No position ids provided")
        for position_id in command.ids:
            await self._repository.restore_position(position_id)

    @distributed_trace()
    async def assign_position(self, position_id: UUID, command: AssignPositionCommand) -> None:
        if not await self._repository.get_by_id(position_id):
            raise NotFoundException(detail=f"Position {position_id} not found")
        await self._repository.assign_incumbent(
            position_id=position_id,
            user_id=command.user_id,
            start_at=command.start_at,
        )
