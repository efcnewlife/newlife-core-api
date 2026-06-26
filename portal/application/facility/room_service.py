"""
Facility room application service.
"""
import uuid
from typing import Any, Optional
from uuid import UUID

from portal.application.facility.commands import (
    BulkIdsCommand,
    CreateRoomCommand,
    DeleteCommand,
    PagesQueryCommand,
    UpdateRoomCommand,
)
from portal.application.facility.results import CreateIdResult, RoomDetailResult, RoomListResult, RoomPageResult
from portal.exceptions.responses import ApiBaseException, BadRequestException, ConflictErrorException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.tracing.distributed_trace import distributed_trace


class RoomService:
    """Admin facility room use cases."""

    def __init__(self, room_repository: RoomRepository):
        self._repository = room_repository
        self._req_ctx: Optional[RequestContext] = get_request_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    def _build_translation_payloads(
        self,
        command: CreateRoomCommand | UpdateRoomCommand,
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

    async def _validate_and_upsert_translations(self, room_id: UUID, translation_payloads: list) -> None:
        if not translation_payloads:
            return
        locale_ids = [item["locale_id"] for item in translation_payloads]
        active_locale_ids = await self._repository.fetch_active_locale_ids(locale_ids)
        if len(active_locale_ids) != len(set(locale_ids)):
            raise BadRequestException(detail="Invalid or inactive locale_id in translations")
        rows = [dict(room_id=room_id, **item) for item in translation_payloads]
        await self._repository.upsert_translations(rows)

    @distributed_trace()
    async def get_room_pages(self, command: PagesQueryCommand) -> RoomPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return RoomPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_room_list(self) -> RoomListResult:
        items = await self._repository.list_active(self._resolved_locale_id())
        return RoomListResult(items=items)

    @distributed_trace()
    async def get_room_by_id(
        self,
        room_id: UUID,
        all_locales: bool = False,
    ) -> Optional[RoomDetailResult]:
        return await self._repository.get_by_id(
            room_id,
            self._resolved_locale_id(),
            all_locales=all_locales,
        )

    @distributed_trace()
    async def create_room(self, command: CreateRoomCommand) -> CreateIdResult:
        room_id = uuid.uuid4()
        translation_payloads = self._build_translation_payloads(command)
        if not translation_payloads:
            raise BadRequestException(detail="translations are required")
        try:
            payload = {
                "id": room_id,
                "code": command.code,
                "room_number": command.room_number,
                "capacity": command.capacity,
                "is_active": command.is_active,
            }
            if command.sequence is not None:
                payload["sequence"] = command.sequence
            await self._repository.insert_room(payload)
            await self._validate_and_upsert_translations(room_id, translation_payloads)
        except ApiBaseException:
            raise
        except Exception as error:
            if self._repository.is_unique_violation(error):
                raise ConflictErrorException(detail="Room code already exists", debug_detail=str(error))
            raise ApiBaseException(status_code=500, detail="Internal Server Error", debug_detail=str(error))
        return CreateIdResult(id=room_id)

    @distributed_trace()
    async def update_room(self, room_id: UUID, command: UpdateRoomCommand) -> None:
        existing = await self._repository.get_by_id(room_id, self._resolved_locale_id())
        if not existing:
            raise NotFoundException(detail=f"Room {room_id} not found")
        values = {
            "room_number": command.room_number,
            "capacity": command.capacity,
            "is_active": command.is_active,
        }
        if command.sequence is not None:
            values["sequence"] = command.sequence
        affected = await self._repository.update_room(room_id, values)
        if affected == 0:
            raise NotFoundException(detail=f"Room {room_id} not found")
        translation_payloads = self._build_translation_payloads(command)
        if translation_payloads:
            await self._validate_and_upsert_translations(room_id, translation_payloads)

    @distributed_trace()
    async def delete_room(self, room_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_by_id(room_id, self._resolved_locale_id()):
            raise NotFoundException(detail=f"Room {room_id} not found")
        if command.permanent:
            await self._repository.delete_hard(room_id)
        else:
            await self._repository.delete_soft(room_id, command.reason)

    @distributed_trace()
    async def restore_rooms(self, command: BulkIdsCommand) -> None:
        if not command.ids:
            raise BadRequestException(detail="No room ids provided")
        for room_id in command.ids:
            await self._repository.restore_room(room_id)
