"""
Facility room slot template application service.
"""
import uuid
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import (
    CreateRoomSlotTemplateCommand,
    DeleteCommand,
    PagesQueryCommand,
    UpdateRoomSlotTemplateCommand,
)
from portal.application.facility.results import (
    CreateIdResult,
    RoomSlotTemplateListResult,
    RoomSlotTemplatePageResult,
    RoomSlotTemplateResult,
)
from portal.domain.facility.days_of_week_mask import days_to_mask
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import (
    RoomSlotTemplateRepository,
)
from portal.libs.tracing.distributed_trace import distributed_trace


class RoomSlotTemplateService:
    """Admin room slot template use cases."""

    def __init__(
        self,
        room_slot_template_repository: RoomSlotTemplateRepository,
        room_repository: RoomRepository,
    ):
        self._repository = room_slot_template_repository
        self._room_repository = room_repository

    def _validate_time_window(self, command: CreateRoomSlotTemplateCommand | UpdateRoomSlotTemplateCommand) -> None:
        if command.start_time >= command.end_time:
            raise BadRequestException(detail="start_time must be before end_time")
        if command.slot_duration_minutes <= 0:
            raise BadRequestException(detail="slot_duration_minutes must be positive")
        if command.effective_from and command.effective_to and command.effective_from > command.effective_to:
            raise BadRequestException(detail="effective_from must be on or before effective_to")

    def _encode_days_mask(self, command: CreateRoomSlotTemplateCommand | UpdateRoomSlotTemplateCommand) -> int:
        try:
            return days_to_mask(command.days_of_week)
        except ValueError as exc:
            raise BadRequestException(detail=str(exc)) from exc

    async def _assert_no_overlap(
        self,
        command: CreateRoomSlotTemplateCommand | UpdateRoomSlotTemplateCommand,
        days_of_week_mask: int,
        exclude_template_id: Optional[UUID] = None,
    ) -> None:
        if not command.is_active:
            return
        candidates = await self._repository.list_active_overlapping_candidates(
            facility_id=command.facility_id,
            days_of_week_mask=days_of_week_mask,
            exclude_template_id=exclude_template_id,
        )
        for candidate in candidates:
            if not self._repository.effective_dates_overlap(
                command.effective_from,
                command.effective_to,
                candidate.effective_from,
                candidate.effective_to,
            ):
                continue
            if self._repository.time_ranges_overlap(
                command.start_time,
                command.end_time,
                candidate.start_time,
                candidate.end_time,
            ):
                raise BadRequestException(
                    detail="Slot template overlaps an existing active template for the same room and weekday",
                )

    @distributed_trace()
    async def get_template_pages(
        self,
        command: PagesQueryCommand,
        facility_id: Optional[UUID] = None,
    ) -> RoomSlotTemplatePageResult:
        items, count = await self._repository.fetch_pages(command, facility_id)
        return RoomSlotTemplatePageResult(
            page=command.page,
            page_size=command.page_size,
            total=count,
            items=items,
        )

    @distributed_trace()
    async def get_template_list(self, facility_id: UUID) -> RoomSlotTemplateListResult:
        items = await self._repository.list_by_facility(facility_id)
        return RoomSlotTemplateListResult(items=items)

    @distributed_trace()
    async def get_template_by_id(self, template_id: UUID) -> Optional[RoomSlotTemplateResult]:
        return await self._repository.get_by_id(template_id)

    @distributed_trace()
    async def create_template(self, command: CreateRoomSlotTemplateCommand) -> CreateIdResult:
        if not await self._room_repository.exists_by_id(command.facility_id):
            raise NotFoundException(detail=f"Room {command.facility_id} not found")
        self._validate_time_window(command)
        days_of_week_mask = self._encode_days_mask(command)
        await self._assert_no_overlap(command, days_of_week_mask)
        template_id = uuid.uuid4()
        await self._repository.insert_template(
            {
                "id": template_id,
                "facility_id": command.facility_id,
                "name": command.name,
                "days_of_week_mask": days_of_week_mask,
                "start_time": command.start_time,
                "end_time": command.end_time,
                "slot_duration_minutes": command.slot_duration_minutes,
                "is_active": command.is_active,
                "effective_from": command.effective_from,
                "effective_to": command.effective_to,
            }
        )
        return CreateIdResult(id=template_id)

    @distributed_trace()
    async def update_template(self, template_id: UUID, command: UpdateRoomSlotTemplateCommand) -> None:
        existing = await self._repository.get_by_id(template_id)
        if not existing:
            raise NotFoundException(detail=f"Slot template {template_id} not found")
        if not await self._room_repository.exists_by_id(command.facility_id):
            raise NotFoundException(detail=f"Room {command.facility_id} not found")
        self._validate_time_window(command)
        days_of_week_mask = self._encode_days_mask(command)
        await self._assert_no_overlap(command, days_of_week_mask, exclude_template_id=template_id)
        affected = await self._repository.update_template(
            template_id,
            {
                "facility_id": command.facility_id,
                "name": command.name,
                "days_of_week_mask": days_of_week_mask,
                "start_time": command.start_time,
                "end_time": command.end_time,
                "slot_duration_minutes": command.slot_duration_minutes,
                "is_active": command.is_active,
                "effective_from": command.effective_from,
                "effective_to": command.effective_to,
            },
        )
        if affected == 0:
            raise NotFoundException(detail=f"Slot template {template_id} not found")

    @distributed_trace()
    async def delete_template(self, template_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_by_id(template_id):
            raise NotFoundException(detail=f"Slot template {template_id} not found")
        if command.permanent:
            await self._repository.delete_hard(template_id)
        else:
            await self._repository.delete_soft(template_id, command.reason)

    @distributed_trace()
    async def restore_template(self, template_id: UUID) -> None:
        await self._repository.restore_template(template_id)
