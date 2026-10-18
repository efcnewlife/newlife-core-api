"""
AvailabilityService unit tests (Timetable cells, visibility, contacts).
"""

from datetime import date, datetime, time, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.content.results import FileGridItemResult
from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.commands import RoomAvailabilityQueryCommand
from portal.application.facility.results import (
    RecurringOccupyingBookingResult,
    RoomBlackoutResult,
    RoomDetailResult,
    RoomListItemResult,
    RoomSlotTemplateResult,
)
from portal.application.org.results import MinistryDetailResult, MinistryMemberResult
from portal.domain.facility.constants import TIMETABLE_CELLS_PER_DAY, RoomBlackoutKind, TimetableCellState, TimetableOccupancyKind
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import ForbiddenException
from portal.libs.contexts.user_context import UserContext, set_user_context
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubFileService,
    StubMinistryRepository,
    StubRoomBlackoutRepository,
    StubRoomRepository,
    StubRoomSlotTemplateRepository,
)
from tests.fixtures.system.stubs import StubSettingService

DAY = date(2026, 7, 20)  # Monday
TZ = ZoneInfo("America/Toronto")


def _utc(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(DAY, time(hour, minute), tzinfo=TZ).astimezone(timezone.utc)


class _StubRoomRepository(StubRoomRepository):
    def __init__(self, rooms: list[RoomListItemResult]):
        super().__init__(existing_ids={r.id for r in rooms})
        self._rooms = rooms

    async def list_active(self, locale_id):
        return list(self._rooms)

    async def get_by_id(self, room_id, locale_id):
        for room in self._rooms:
            if room.id == room_id:
                return RoomDetailResult(id=room.id, code=room.code, name=room.name, room_number=room.room_number, capacity=50, is_active=room.is_active)
        return None


class _StubSlotTemplateRepository(StubRoomSlotTemplateRepository):
    def __init__(self, templates: list[RoomSlotTemplateResult]):
        super().__init__()
        self._templates = templates

    async def list_active_for_day(self, facility_id, day_of_week):
        return [item for item in self._templates if item.facility_id == facility_id and (item.days_of_week_mask & (1 << day_of_week)) != 0]


def _room_and_template(room_id=None, start=time(9, 0), end=time(12, 0), duration=60):
    room_id = room_id or uuid4()
    rooms = [RoomListItemResult(id=room_id, code="gym", name="Gym", room_number="1", is_active=True)]
    templates = [
        RoomSlotTemplateResult(
            id=uuid4(), facility_id=room_id, name="Day", days_of_week_mask=127, start_time=start, end_time=end, slot_duration_minutes=duration, is_active=True
        )
    ]
    return room_id, rooms, templates


def _make_availability_service(rooms, templates, blackouts=None, file_service=None, setting_service=None, booking_repository=None, ministry_repository=None):
    return AvailabilityService(
        _StubRoomRepository(rooms),
        _StubSlotTemplateRepository(templates),
        booking_repository or StubBookingRepository(has_overlap=False),
        ministry_repository or StubMinistryRepository(),
        StubRoomBlackoutRepository(for_room_day=blackouts or []),
        setting_service or StubSettingService(),
        file_service or StubFileService(),
    )


@pytest.mark.asyncio
async def test_availability_excludes_blackout_overlap():
    room_id, rooms, templates = _room_and_template()
    blackouts = [
        RoomBlackoutResult(
            id=uuid4(),
            facility_id=None,
            name="Campus closed",
            reason="Holiday",
            kind=RoomBlackoutKind.ONE_OFF.value,
            blackout_date=DAY,
            days_of_week_mask=None,
            start_time=time(10, 0),
            end_time=time(11, 0),
            is_active=True,
        )
    ]
    service = _make_availability_service(rooms, templates, blackouts)
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY))
    assert len(result.items) == 1
    assert result.facility_timezone == "America/Toronto"
    assert len(result.items[0].cells) == TIMETABLE_CELLS_PER_DAY
    by_start = {cell.start: cell.state for cell in result.items[0].cells}
    assert by_start["09:00"] == TimetableCellState.AVAILABLE.value
    assert by_start["10:00"] == TimetableCellState.CLOSED.value
    assert by_start["11:00"] == TimetableCellState.AVAILABLE.value
    assert by_start["08:00"] == TimetableCellState.CLOSED.value
    am = result.items[0].availability.am
    starts = [slot.start for slot in am]
    assert "09:00" in starts
    assert "11:00" in starts
    assert result.items[0].photo_urls == []
    assert result.items[0].templates[0].slot_duration_minutes == 60
    assert result.items[0].events == []


@pytest.mark.asyncio
async def test_availability_includes_photo_urls_in_gallery_order():
    room_id, rooms, templates = _room_and_template()
    first = FileGridItemResult(id=uuid4(), original_name="a.jpg", key="a", storage="s3", bucket="b", region="ca-central-1", url="https://cdn.example/a.jpg")
    second = FileGridItemResult(id=uuid4(), original_name="b.jpg", key="b", storage="s3", bucket="b", region="ca-central-1", url="https://cdn.example/b.jpg")
    service = _make_availability_service(rooms, templates, file_service=StubFileService(files_by_resource={room_id: [first, second]}))
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY))
    assert result.items[0].photo_urls == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]


@pytest.mark.asyncio
async def test_availability_includes_live_max_booking_lines():
    service = _make_availability_service([], [], setting_service=StubSettingService(max_booking_lines=10))
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY))
    assert result.max_booking_lines == 10
    assert result.facility_timezone == "America/Toronto"


@pytest.mark.asyncio
async def test_personal_hides_fully_occupied_room_ministry_keeps_it():
    room_id, rooms, templates = _room_and_template()
    occupying = [
        RecurringOccupyingBookingResult(
            booking_id=uuid4(),
            user_id=uuid4(),
            ministry_id=None,
            facility_ids=[room_id],
            start_at=_utc(9),
            end_at=_utc(12),
            booker_display_name="Jane Booker",
            booker_email="jane@example.com",
        )
    ]
    booking_repo = StubBookingRepository(occupying_bookings=occupying)
    personal = _make_availability_service(rooms, templates, booking_repository=booking_repo)
    personal_result = await personal.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY))
    assert personal_result.items == []

    ministry_id = uuid4()
    user_id = uuid4()
    set_user_context(UserContext(user_id=user_id, email="steward@efcnewlife.org"))
    ministry_repo = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Choir", status=MinistryStatus.ACTIVE.value, has_priority_booking=False, is_active=True)
        },
        booking_member_user_ids={user_id},
    )
    ministry_service = _make_availability_service(rooms, templates, booking_repository=booking_repo, ministry_repository=ministry_repo)
    ministry_result = await ministry_service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY, ministry_id=ministry_id))
    assert len(ministry_result.items) == 1
    by_start = {cell.start: cell.state for cell in ministry_result.items[0].cells}
    assert by_start["09:00"] == TimetableCellState.UNAVAILABLE.value
    assert ministry_result.items[0].events[0].occupancy_kind == TimetableOccupancyKind.RENTAL.value
    assert ministry_result.items[0].events[0].contact_display_name == "Jane Booker"
    assert ministry_result.items[0].events[0].contact_email == "jane@example.com"
    assert "09:00" not in [slot.start for slot in ministry_result.items[0].availability.am]


@pytest.mark.asyncio
async def test_priority_ministry_marks_future_rental_override():
    future_day = date(2026, 11, 16)  # Monday after "today" in the agent clock
    room_id, rooms, templates = _room_and_template()
    start_at = datetime.combine(future_day, time(10, 0), tzinfo=TZ).astimezone(timezone.utc)
    end_at = datetime.combine(future_day, time(11, 0), tzinfo=TZ).astimezone(timezone.utc)
    occupying = [
        RecurringOccupyingBookingResult(booking_id=uuid4(), user_id=uuid4(), ministry_id=None, facility_ids=[room_id], start_at=start_at, end_at=end_at)
    ]
    ministry_id = uuid4()
    user_id = uuid4()
    set_user_context(UserContext(user_id=user_id, email="steward@efcnewlife.org"))
    ministry_repo = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Priority", status=MinistryStatus.ACTIVE.value, has_priority_booking=True, is_active=True)
        },
        booking_member_user_ids={user_id},
    )
    service = _make_availability_service(
        rooms, templates, booking_repository=StubBookingRepository(occupying_bookings=occupying), ministry_repository=ministry_repo
    )
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=future_day, ministry_id=ministry_id))
    by_start = {cell.start: cell.state for cell in result.items[0].cells}
    assert by_start["10:00"] == TimetableCellState.OVERRIDE.value
    assert result.items[0].events[0].is_overridable is True
    assert "10:00" not in [slot.start for slot in result.items[0].availability.am]


@pytest.mark.asyncio
async def test_ministry_occupancy_exposes_primary_steward_contact():
    room_id, rooms, templates = _room_and_template()
    occupying_ministry_id = uuid4()
    occupying = [
        RecurringOccupyingBookingResult(
            booking_id=uuid4(),
            user_id=uuid4(),
            ministry_id=occupying_ministry_id,
            ministry_name="Youth",
            facility_ids=[room_id],
            start_at=_utc(10),
            end_at=_utc(11),
        )
    ]
    viewer_ministry_id = uuid4()
    user_id = uuid4()
    set_user_context(UserContext(user_id=user_id, email="steward@efcnewlife.org"))
    ministry_repo = StubMinistryRepository(
        ministry_by_id={
            viewer_ministry_id: MinistryDetailResult(
                id=viewer_ministry_id, name="Choir", status=MinistryStatus.ACTIVE.value, has_priority_booking=False, is_active=True
            ),
            occupying_ministry_id: MinistryDetailResult(
                id=occupying_ministry_id, name="Youth", status=MinistryStatus.ACTIVE.value, has_priority_booking=False, is_active=True
            ),
        },
        booking_member_user_ids={user_id},
        members_by_ministry={
            occupying_ministry_id: [
                MinistryMemberResult(
                    user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat Steward", email="pat.steward@efcnewlife.org"
                )
            ]
        },
    )
    service = _make_availability_service(
        rooms, templates, booking_repository=StubBookingRepository(occupying_bookings=occupying), ministry_repository=ministry_repo
    )
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY, ministry_id=viewer_ministry_id))
    event = result.items[0].events[0]
    assert event.occupancy_kind == TimetableOccupancyKind.MINISTRY.value
    assert event.ministry_name == "Youth"
    assert event.contact_display_name == "Pat Steward"
    assert event.contact_email == "pat.steward@efcnewlife.org"
    assert result.items[0].cells[20].event_indices or any(cell.event_indices for cell in result.items[0].cells)


@pytest.mark.asyncio
async def test_forged_ministry_context_is_rejected():
    room_id, rooms, templates = _room_and_template()
    ministry_id = uuid4()
    user_id = uuid4()
    set_user_context(UserContext(user_id=user_id, email="outsider@efcnewlife.org"))
    ministry_repo = StubMinistryRepository(
        ministry_by_id={
            ministry_id: MinistryDetailResult(id=ministry_id, name="Choir", status=MinistryStatus.ACTIVE.value, has_priority_booking=False, is_active=True)
        },
        booking_member_user_ids=set(),
    )
    service = _make_availability_service(rooms, templates, ministry_repository=ministry_repo)
    with pytest.raises(ForbiddenException):
        await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY, ministry_id=ministry_id))


@pytest.mark.asyncio
async def test_room_without_applicable_template_is_omitted():
    room_id = uuid4()
    rooms = [RoomListItemResult(id=room_id, code="gym", name="Gym", room_number="1", is_active=True)]
    service = _make_availability_service(rooms, [])
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=DAY))
    assert result.items == []
