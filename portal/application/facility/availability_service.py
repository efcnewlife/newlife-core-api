"""
Member room availability application service.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.commands import RoomAvailabilityQueryCommand
from portal.application.facility.results import DayAvailabilityResult, RoomAvailabilityListResult, RoomAvailabilityResult, TimeSlotResult
from portal.application.system.setting_service import SettingService
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import BadRequestException, ForbiddenException
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import RoomSlotTemplateRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class AvailabilityService:
    """Compute room availability for a calendar date."""

    def __init__(
        self,
        room_repository: RoomRepository,
        room_slot_template_repository: RoomSlotTemplateRepository,
        booking_repository: BookingRepository,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
    ):
        self._room_repository = room_repository
        self._slot_template_repository = room_slot_template_repository
        self._booking_repository = booking_repository
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    async def _validate_ministry_gate(self, ministry_id: Optional[UUID]) -> None:
        if ministry_id is None:
            return
        status = await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(detail="Ministry must be active for booking")
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required for ministry booking")
        if not await self._ministry_repository.is_user_booking_member(ministry_id, user_id):
            raise ForbiddenException(detail="User is not a ministry owner")

    @staticmethod
    def _combine_local(day: date, value: time, tz: ZoneInfo) -> datetime:
        return datetime.combine(day, value, tzinfo=tz).astimezone(timezone.utc)

    @staticmethod
    def _format_local(dt: datetime, tz: ZoneInfo) -> str:
        local = dt.astimezone(tz)
        return local.strftime("%H:%M")

    @distributed_trace()
    async def get_rooms_availability(self, command: RoomAvailabilityQueryCommand) -> RoomAvailabilityListResult:
        await self._validate_ministry_gate(command.ministry_id)
        local_tz = await self._setting_service.get_facility_timezone()
        day = command.target_date
        day_of_week = day.weekday()
        rooms = await self._room_repository.list_active(self._resolved_locale_id())
        items: list[RoomAvailabilityResult] = []

        for room in rooms:
            templates = await self._slot_template_repository.list_active_for_day(room.id, day_of_week)
            blackouts = await self._blackout_repository.list_active_for_room_day(room.id, day)
            am_slots: list[TimeSlotResult] = []
            pm_slots: list[TimeSlotResult] = []
            for template in templates:
                if template.effective_from and day < template.effective_from:
                    continue
                if template.effective_to and day > template.effective_to:
                    continue
                duration = max(15, int(template.slot_duration_minutes or 60))
                cursor = self._combine_local(day, template.start_time, local_tz)
                window_end = self._combine_local(day, template.end_time, local_tz)
                while cursor + timedelta(minutes=duration) <= window_end:
                    slot_end = cursor + timedelta(minutes=duration)
                    local_start = cursor.astimezone(local_tz).time()
                    local_end = slot_end.astimezone(local_tz).time()
                    if self._blackout_repository.slot_overlaps_blackouts(blackouts, local_start, local_end):
                        cursor = slot_end
                        continue
                    overlap = await self._booking_repository.has_confirmed_slot_overlap(facility_id=room.id, start_at=cursor, end_at=slot_end)
                    if not overlap:
                        slot = TimeSlotResult(start=self._format_local(cursor, local_tz), end=self._format_local(slot_end, local_tz))
                        local_hour = cursor.astimezone(local_tz).hour
                        if local_hour < 12:
                            am_slots.append(slot)
                        else:
                            pm_slots.append(slot)
                    cursor = slot_end

            if am_slots or pm_slots:
                detail = await self._room_repository.get_by_id(room.id, self._resolved_locale_id())
                capacity = detail.capacity if detail else None
                items.append(
                    RoomAvailabilityResult(
                        id=room.id,
                        code=room.code,
                        name=room.name,
                        room_number=room.room_number,
                        capacity=capacity,
                        is_active=room.is_active,
                        availability=DayAvailabilityResult(am=am_slots, pm=pm_slots),
                    )
                )

        return RoomAvailabilityListResult(date=day, items=items)
