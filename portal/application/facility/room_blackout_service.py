"""
Facility room blackout application service.
"""

import uuid
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import CreateRoomBlackoutCommand, DeleteCommand, PagesQueryCommand, UpdateRoomBlackoutCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import BlackoutImpactResult, CreateIdResult, RoomBlackoutListResult, RoomBlackoutPageResult, RoomBlackoutResult
from portal.domain.facility.constants import FacilityErrorCode, RoomBlackoutKind
from portal.domain.facility.days_of_week_mask import days_to_mask
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.tracing.distributed_trace import distributed_trace


class RoomBlackoutService:
    """Admin room blackout use cases."""

    def __init__(self, room_blackout_repository: RoomBlackoutRepository, room_repository: RoomRepository, recurring_booking_service: RecurringBookingService):
        self._repository = room_blackout_repository
        self._room_repository = room_repository
        self._recurring_booking_service = recurring_booking_service

    def _normalize_kind(self, kind: str) -> str:
        value = (kind or "").strip().lower()
        if value not in {RoomBlackoutKind.ONE_OFF.value, RoomBlackoutKind.RECURRING.value}:
            raise BadRequestException(detail="kind must be one_off or recurring")
        return value

    def _validate_command(self, command: CreateRoomBlackoutCommand | UpdateRoomBlackoutCommand) -> tuple[str, Optional[int]]:
        if not (command.reason or "").strip():
            raise BadRequestException(detail="reason is required")
        if command.start_time >= command.end_time:
            raise BadRequestException(detail="start_time must be before end_time")
        if command.effective_from and command.effective_to and command.effective_from > command.effective_to:
            raise BadRequestException(detail="effective_from must be on or before effective_to")

        kind = self._normalize_kind(command.kind)
        days_of_week_mask: Optional[int] = None

        if kind == RoomBlackoutKind.ONE_OFF.value:
            if command.blackout_date is None:
                raise BadRequestException(detail="blackout_date is required for one_off blackouts")
            if command.days_of_week:
                raise BadRequestException(detail="days_of_week must be empty for one_off blackouts")
        else:
            if command.blackout_date is not None:
                raise BadRequestException(detail="blackout_date must be empty for recurring blackouts")
            try:
                days_of_week_mask = days_to_mask(command.days_of_week or [])
            except ValueError as exc:
                raise BadRequestException(detail=str(exc)) from exc

        return kind, days_of_week_mask

    async def _assert_room_exists(self, facility_id: Optional[UUID]) -> None:
        if facility_id is None:
            return
        if not await self._room_repository.exists_by_id(facility_id):
            raise NotFoundException(
                detail=f"Room {facility_id} not found", error_code=FacilityErrorCode.ROOM_NOT_FOUND.value, context={"room_id": str(facility_id)}
            )

    async def _assert_no_overlap(
        self,
        command: CreateRoomBlackoutCommand | UpdateRoomBlackoutCommand,
        kind: str,
        days_of_week_mask: Optional[int],
        exclude_blackout_id: Optional[UUID] = None,
    ) -> None:
        if not command.is_active:
            return
        candidates = await self._repository.list_active_overlapping_candidates(
            facility_id=command.facility_id, kind=kind, exclude_blackout_id=exclude_blackout_id
        )
        for candidate in candidates:
            if not self._repository.scopes_overlap(command.facility_id, candidate.facility_id):
                continue
            if not self._repository.time_ranges_overlap(command.start_time, command.end_time, candidate.start_time, candidate.end_time):
                continue
            if kind == RoomBlackoutKind.ONE_OFF.value:
                if candidate.blackout_date != command.blackout_date:
                    continue
            else:
                if candidate.days_of_week_mask is None or days_of_week_mask is None:
                    continue
                if (candidate.days_of_week_mask & days_of_week_mask) == 0:
                    continue
                if not self._repository.effective_dates_overlap(command.effective_from, command.effective_to, candidate.effective_from, candidate.effective_to):
                    continue
            raise BadRequestException(
                detail="Blackout overlaps an existing active blackout for the same scope and time",
                error_code=FacilityErrorCode.BLACKOUT_OVERLAP.value,
                context={"facility_id": str(command.facility_id)} if command.facility_id else None,
            )

    def _to_payload(
        self, command: CreateRoomBlackoutCommand | UpdateRoomBlackoutCommand, kind: str, days_of_week_mask: Optional[int], blackout_id: Optional[UUID] = None
    ) -> dict:
        payload = {
            "facility_id": command.facility_id,
            "name": command.name.strip(),
            "reason": command.reason.strip(),
            "kind": kind,
            "blackout_date": command.blackout_date if kind == RoomBlackoutKind.ONE_OFF.value else None,
            "days_of_week_mask": days_of_week_mask if kind == RoomBlackoutKind.RECURRING.value else None,
            "start_time": command.start_time,
            "end_time": command.end_time,
            "is_active": command.is_active,
            "effective_from": command.effective_from if kind == RoomBlackoutKind.RECURRING.value else None,
            "effective_to": command.effective_to if kind == RoomBlackoutKind.RECURRING.value else None,
        }
        if blackout_id is not None:
            payload["id"] = blackout_id
        return payload

    def _proposed_blackout(
        self, command: CreateRoomBlackoutCommand | UpdateRoomBlackoutCommand, kind: str, days_of_week_mask: Optional[int]
    ) -> RoomBlackoutResult:
        return RoomBlackoutResult(
            facility_id=command.facility_id,
            name=command.name.strip(),
            reason=command.reason.strip(),
            kind=kind,
            blackout_date=command.blackout_date if kind == RoomBlackoutKind.ONE_OFF.value else None,
            days_of_week_mask=days_of_week_mask if kind == RoomBlackoutKind.RECURRING.value else None,
            start_time=command.start_time,
            end_time=command.end_time,
            is_active=command.is_active,
            effective_from=command.effective_from if kind == RoomBlackoutKind.RECURRING.value else None,
            effective_to=command.effective_to if kind == RoomBlackoutKind.RECURRING.value else None,
        )

    @staticmethod
    def _raise_if_impact_unconfirmed(impact: BlackoutImpactResult, confirm_occurrence_ids: Optional[list[UUID]]) -> None:
        if not impact.items:
            return
        confirmed = set(confirm_occurrence_ids or [])
        expected = {item.id for item in impact.items}
        if not confirmed:
            raise BadRequestException(
                detail="Blackout impact confirmation is required", error_code=FacilityErrorCode.BLACKOUT_IMPACT_CONFIRMATION_REQUIRED.value
            )
        if confirmed != expected:
            raise BadRequestException(
                detail="Confirmed occurrence ids must match the current Blackout impact", error_code=FacilityErrorCode.BLACKOUT_IMPACT_MISMATCH.value
            )

    @distributed_trace()
    async def get_blackout_pages(self, command: PagesQueryCommand, facility_id: Optional[UUID] = None) -> RoomBlackoutPageResult:
        items, count = await self._repository.fetch_pages(command, facility_id)
        return RoomBlackoutPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_blackout_list(self, facility_id: Optional[UUID]) -> RoomBlackoutListResult:
        items = await self._repository.list_by_facility(facility_id)
        return RoomBlackoutListResult(items=items)

    @distributed_trace()
    async def get_blackout_by_id(self, blackout_id: UUID) -> Optional[RoomBlackoutResult]:
        return await self._repository.get_by_id(blackout_id)

    @distributed_trace()
    async def preview_blackout_impact(self, command: CreateRoomBlackoutCommand) -> BlackoutImpactResult:
        await self._assert_room_exists(command.facility_id)
        kind, days_of_week_mask = self._validate_command(command)
        proposed = self._proposed_blackout(command, kind, days_of_week_mask)
        return await self._recurring_booking_service.preview_blackout_impact(proposed)

    @distributed_trace()
    async def create_blackout(self, command: CreateRoomBlackoutCommand) -> CreateIdResult:
        await self._assert_room_exists(command.facility_id)
        kind, days_of_week_mask = self._validate_command(command)
        await self._assert_no_overlap(command, kind, days_of_week_mask)
        proposed = self._proposed_blackout(command, kind, days_of_week_mask)
        impact = await self._recurring_booking_service.preview_blackout_impact(proposed)
        self._raise_if_impact_unconfirmed(impact, command.confirm_occurrence_ids)
        blackout_id = uuid.uuid4()
        await self._repository.insert_blackout(self._to_payload(command, kind, days_of_week_mask, blackout_id=blackout_id))
        if impact.items:
            await self._recurring_booking_service.apply_blackout_impact(impact.items, command.reason.strip())
        return CreateIdResult(id=blackout_id)

    @distributed_trace()
    async def update_blackout(self, blackout_id: UUID, command: UpdateRoomBlackoutCommand) -> None:
        existing = await self._repository.get_by_id(blackout_id)
        if not existing:
            raise NotFoundException(
                detail=f"Blackout {blackout_id} not found", error_code=FacilityErrorCode.BLACKOUT_NOT_FOUND.value, context={"blackout_id": str(blackout_id)}
            )
        await self._assert_room_exists(command.facility_id)
        kind, days_of_week_mask = self._validate_command(command)
        await self._assert_no_overlap(command, kind, days_of_week_mask, exclude_blackout_id=blackout_id)
        affected = await self._repository.update_blackout(blackout_id, self._to_payload(command, kind, days_of_week_mask))
        if affected == 0:
            raise NotFoundException(
                detail=f"Blackout {blackout_id} not found", error_code=FacilityErrorCode.BLACKOUT_NOT_FOUND.value, context={"blackout_id": str(blackout_id)}
            )

    @distributed_trace()
    async def delete_blackout(self, blackout_id: UUID, command: DeleteCommand) -> None:
        if not await self._repository.get_by_id(blackout_id):
            raise NotFoundException(
                detail=f"Blackout {blackout_id} not found", error_code=FacilityErrorCode.BLACKOUT_NOT_FOUND.value, context={"blackout_id": str(blackout_id)}
            )
        if command.permanent:
            await self._repository.delete_hard(blackout_id)
        else:
            await self._repository.delete_soft(blackout_id, command.reason)

    @distributed_trace()
    async def restore_blackout(self, blackout_id: UUID) -> None:
        await self._repository.restore_blackout(blackout_id)
