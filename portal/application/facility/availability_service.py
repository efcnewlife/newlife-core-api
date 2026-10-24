"""
Member room availability application service.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.content.file_service import FileService
from portal.application.facility.commands import RoomAvailabilityQueryCommand
from portal.application.facility.opening_hours import merge_open_windows
from portal.application.facility.results import (
    DayAvailabilityResult,
    RoomAvailabilityCellResult,
    RoomAvailabilityEventResult,
    RoomAvailabilityListResult,
    RoomAvailabilityResult,
    RoomAvailabilityTemplateResult,
    RoomBlackoutResult,
    RoomSlotTemplateResult,
    TimeSlotResult,
)
from portal.application.facility.timetable_projection import (
    OccupancyInterval,
    OpenInterval,
    classify_cell,
    day_cell_bounds,
    format_local_hm,
    intervals_overlap,
    merge_contiguous_free_slots,
    project_ministry_events,
    should_include_room,
)
from portal.application.system.setting_service import SettingService
from portal.domain.content.constants import FILE_RESOURCE_KIND_FACILITY_ROOM
from portal.domain.facility.constants import ROOM_GALLERY_MAX_FILES, TIMETABLE_CELLS_PER_DAY, FacilityErrorCode
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
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
    """Compute context-aware room Timetable availability for a calendar date."""

    def __init__(
        self,
        room_repository: RoomRepository,
        room_slot_template_repository: RoomSlotTemplateRepository,
        booking_repository: BookingRepository,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
        file_service: FileService,
        now_utc: Optional[Callable[[], datetime]] = None,
    ):
        self._room_repository = room_repository
        self._slot_template_repository = room_slot_template_repository
        self._booking_repository = booking_repository
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._file_service = file_service
        self._now_utc = now_utc or (lambda: datetime.now(timezone.utc))
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    async def _resolve_ministry_context(self, ministry_id: Optional[UUID]) -> tuple[bool, bool]:
        """Return (is_ministry_context, is_priority). Rejects forged or unauthorized Ministry context."""
        if ministry_id is None:
            return False, False
        ministry = await self._ministry_repository.get_by_id(ministry_id, locale_id=self._resolved_locale_id())
        status = ministry.status if ministry else await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(detail="Ministry must be active for booking")
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required for ministry booking")
        if not await self._ministry_repository.is_user_booking_member(ministry_id, user_id):
            raise ForbiddenException(detail="User is not a ministry owner")
        is_priority = bool(ministry.has_priority_booking) if ministry else False
        return True, is_priority

    @staticmethod
    def _combine_local(day: date, value: time, tz: ZoneInfo) -> datetime:
        return datetime.combine(day, value, tzinfo=tz).astimezone(timezone.utc)

    def _applicable_templates(self, templates: list[RoomSlotTemplateResult], day: date) -> list[RoomSlotTemplateResult]:
        applicable: list[RoomSlotTemplateResult] = []
        for template in templates:
            if template.effective_from and day < template.effective_from:
                continue
            if template.effective_to and day > template.effective_to:
                continue
            applicable.append(template)
        return applicable

    def _build_open_windows(
        self, day: date, templates: list[RoomSlotTemplateResult], blackouts: list[RoomBlackoutResult], local_tz: ZoneInfo
    ) -> list[OpenInterval]:
        template_windows: list[tuple[datetime, datetime]] = []
        for template in templates:
            start_at = self._combine_local(day, template.start_time, local_tz)
            end_at = self._combine_local(day, template.end_time, local_tz)
            if start_at < end_at:
                template_windows.append((start_at, end_at))
        merged = merge_open_windows(template_windows)
        if not blackouts:
            return [OpenInterval(start_at=start_at, end_at=end_at) for start_at, end_at in merged]
        open_windows: list[OpenInterval] = []
        for window_start, window_end in merged:
            segments = [(window_start, window_end)]
            for blackout in blackouts:
                blackout_start = self._combine_local(day, blackout.start_time, local_tz)
                blackout_end = self._combine_local(day, blackout.end_time, local_tz)
                next_segments: list[tuple[datetime, datetime]] = []
                for seg_start, seg_end in segments:
                    if not intervals_overlap(seg_start, seg_end, blackout_start, blackout_end):
                        next_segments.append((seg_start, seg_end))
                        continue
                    if seg_start < blackout_start:
                        next_segments.append((seg_start, min(seg_end, blackout_start)))
                    if blackout_end < seg_end:
                        next_segments.append((max(seg_start, blackout_end), seg_end))
                segments = next_segments
            open_windows.extend(OpenInterval(start_at=seg_start, end_at=seg_end) for seg_start, seg_end in segments if seg_start < seg_end)
        return open_windows

    async def _primary_steward_contact(self, ministry_id: UUID) -> tuple[Optional[str], Optional[str]]:
        members = await self._ministry_repository.list_members(ministry_id)
        primary = next((member for member in members if member.member_role == MinistryMemberRole.PRIMARY.value), None)
        if primary is None:
            return None, None
        display_name = primary.display_name or primary.email
        return display_name, primary.email

    async def _occupancy_for_room_day(
        self, *, facility_id: UUID, day: date, local_tz: ZoneInfo, is_ministry_context: bool, is_priority: bool
    ) -> list[OccupancyInterval]:
        day_start = self._combine_local(day, time.min, local_tz)
        day_end = day_start + timedelta(days=1)
        rows = await self._booking_repository.list_occupying_slots(
            facility_id=facility_id, start_at=day_start, end_at=day_end, locale_id=self._resolved_locale_id()
        )
        steward_contact_by_ministry: dict[UUID, tuple[Optional[str], Optional[str]]] = {}
        intervals: list[OccupancyInterval] = []
        for row in rows:
            ministry_name: Optional[str] = row.ministry_name
            contact_display_name: Optional[str] = None
            contact_email: Optional[str] = None
            if is_ministry_context:
                if row.ministry_id:
                    if not ministry_name:
                        ministry = await self._ministry_repository.get_by_id(row.ministry_id, locale_id=self._resolved_locale_id())
                        ministry_name = ministry.name if ministry else None
                    if row.ministry_id not in steward_contact_by_ministry:
                        steward_contact_by_ministry[row.ministry_id] = await self._primary_steward_contact(row.ministry_id)
                    contact_display_name, contact_email = steward_contact_by_ministry[row.ministry_id]
                elif not is_priority:
                    contact_display_name = row.booker_display_name
                    contact_email = row.booker_email
            intervals.append(
                OccupancyInterval(
                    booking_id=row.booking_id,
                    start_at=row.start_at,
                    end_at=row.end_at,
                    booking_start_at=row.start_at,
                    ministry_id=row.ministry_id,
                    ministry_name=ministry_name,
                    contact_display_name=contact_display_name,
                    contact_email=contact_email,
                )
            )
        return intervals

    def _ampm_from_free_slots(self, free_slots: list[tuple[datetime, datetime]], local_tz: ZoneInfo) -> DayAvailabilityResult:
        am_slots: list[TimeSlotResult] = []
        pm_slots: list[TimeSlotResult] = []
        for start_at, end_at in free_slots:
            slot = TimeSlotResult(start=format_local_hm(start_at, local_tz), end=format_local_hm(end_at, local_tz))
            if start_at.astimezone(local_tz).hour < 12:
                am_slots.append(slot)
            else:
                pm_slots.append(slot)
        return DayAvailabilityResult(am=am_slots, pm=pm_slots)

    @distributed_trace()
    async def get_rooms_availability(self, command: RoomAvailabilityQueryCommand) -> RoomAvailabilityListResult:
        local_tz = await self._setting_service.get_facility_timezone()
        now_utc = self._now_utc()
        day = command.target_date
        if day < now_utc.astimezone(local_tz).date():
            raise BadRequestException(detail="Date must be today or later", error_code=FacilityErrorCode.AVAILABILITY_DATE_IN_PAST.value)
        is_ministry_context, is_priority = await self._resolve_ministry_context(command.ministry_id)
        max_booking_lines = await self._setting_service.get_max_booking_lines()
        day_of_week = day.weekday()
        cell_bounds = day_cell_bounds(day, local_tz)
        rooms = await self._room_repository.list_active(self._resolved_locale_id())
        items: list[RoomAvailabilityResult] = []

        for room in rooms:
            templates = self._applicable_templates(await self._slot_template_repository.list_active_for_day(room.id, day_of_week), day)
            blackouts = await self._blackout_repository.list_active_for_room_day(room.id, day)
            open_windows = self._build_open_windows(day, templates, blackouts, local_tz)
            occupancies = await self._occupancy_for_room_day(
                facility_id=room.id, day=day, local_tz=local_tz, is_ministry_context=is_ministry_context, is_priority=is_priority
            )
            cell_states = [
                classify_cell(
                    cell_start=start_at, cell_end=end_at, open_windows=open_windows, occupancies=occupancies, is_priority=is_priority, now_utc=now_utc
                )
                for start_at, end_at in cell_bounds
            ]
            if not should_include_room(is_ministry_context=is_ministry_context, open_windows=open_windows, cell_states=cell_states):
                continue

            events: list[RoomAvailabilityEventResult] = []
            event_indices_by_cell: list[list[int]] = [[] for _ in range(TIMETABLE_CELLS_PER_DAY)]
            if is_ministry_context:
                projected = project_ministry_events(occupancies=occupancies, open_windows=open_windows, is_priority=is_priority, now_utc=now_utc)
                for event_index, event in enumerate(projected):
                    events.append(
                        RoomAvailabilityEventResult(
                            start=format_local_hm(event.start_at, local_tz),
                            end=format_local_hm(event.end_at, local_tz),
                            occupancy_kind=event.occupancy_kind,
                            is_overridable=event.is_overridable,
                            ministry_name=event.ministry_name,
                            contact_display_name=event.contact_display_name,
                            contact_email=event.contact_email,
                        )
                    )
                    for cell_index, (cell_start, cell_end) in enumerate(cell_bounds):
                        if intervals_overlap(cell_start, cell_end, event.start_at, event.end_at):
                            event_indices_by_cell[cell_index].append(event_index)

            cells = [
                RoomAvailabilityCellResult(
                    start=format_local_hm(start_at, local_tz),
                    end=format_local_hm(end_at, local_tz),
                    state=state.value,
                    event_indices=event_indices_by_cell[index] if is_ministry_context else [],
                )
                for index, ((start_at, end_at), state) in enumerate(zip(cell_bounds, cell_states, strict=True))
            ]
            free_slots = merge_contiguous_free_slots(cell_bounds, cell_states)
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
                    templates=[
                        RoomAvailabilityTemplateResult(
                            start=format_local_hm(self._combine_local(day, template.start_time, local_tz), local_tz),
                            end=format_local_hm(self._combine_local(day, template.end_time, local_tz), local_tz),
                            slot_duration_minutes=max(15, int(template.slot_duration_minutes or 60)),
                        )
                        for template in templates
                    ],
                    cells=cells,
                    events=events,
                    availability=self._ampm_from_free_slots(free_slots, local_tz),
                )
            )

        photo_urls_by_room = await self._file_service.get_signed_urls_by_resource_ids(
            [item.id for item in items], resource_name=FILE_RESOURCE_KIND_FACILITY_ROOM
        )
        for item in items:
            item.photo_urls = photo_urls_by_room.get(item.id, [])[:ROOM_GALLERY_MAX_FILES]

        return RoomAvailabilityListResult(date=day, facility_timezone=str(local_tz), items=items, max_booking_lines=max_booking_lines)
