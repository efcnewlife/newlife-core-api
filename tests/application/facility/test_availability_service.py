"""
AvailabilityService unit tests (blackout filtering).
"""

from datetime import date, time
from uuid import uuid4

import pytest

from portal.application.content.results import FileGridItemResult
from portal.application.facility.availability_service import AvailabilityService
from portal.application.facility.commands import RoomAvailabilityQueryCommand
from portal.application.facility.results import RoomBlackoutResult, RoomDetailResult, RoomListItemResult, RoomSlotTemplateResult
from portal.domain.facility.constants import RoomBlackoutKind
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubFileService,
    StubMinistryRepository,
    StubRoomBlackoutRepository,
    StubRoomRepository,
    StubRoomSlotTemplateRepository,
)
from tests.fixtures.system.stubs import StubSettingService


def _make_availability_service(rooms, templates, blackouts=None, file_service=None):
    return AvailabilityService(
        _StubRoomRepository(rooms),
        _StubSlotTemplateRepository(templates),
        StubBookingRepository(has_overlap=False),
        StubMinistryRepository(),
        StubRoomBlackoutRepository(for_room_day=blackouts or []),
        StubSettingService(),
        file_service or StubFileService(),
    )


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


@pytest.mark.asyncio
async def test_availability_excludes_blackout_overlap():
    room_id = uuid4()
    rooms = [RoomListItemResult(id=room_id, code="gym", name="Gym", room_number="1", is_active=True)]
    templates = [
        RoomSlotTemplateResult(
            id=uuid4(),
            facility_id=room_id,
            name="Day",
            days_of_week_mask=127,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration_minutes=60,
            is_active=True,
        )
    ]
    blackouts = [
        RoomBlackoutResult(
            id=uuid4(),
            facility_id=None,
            name="Campus closed",
            reason="Holiday",
            kind=RoomBlackoutKind.ONE_OFF.value,
            blackout_date=date(2026, 7, 20),
            days_of_week_mask=None,
            start_time=time(10, 0),
            end_time=time(11, 0),
            is_active=True,
        )
    ]
    service = _make_availability_service(rooms, templates, blackouts)
    # 2026-07-20 is Monday
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=date(2026, 7, 20)))
    assert len(result.items) == 1
    am = result.items[0].availability.am
    starts = [slot.start for slot in am]
    assert "09:00" in starts
    assert "11:00" in starts
    assert "10:00" not in starts
    assert result.items[0].photo_urls == []


@pytest.mark.asyncio
async def test_availability_includes_photo_urls_in_gallery_order():
    room_id = uuid4()
    rooms = [RoomListItemResult(id=room_id, code="gym", name="Gym", room_number="1", is_active=True)]
    templates = [
        RoomSlotTemplateResult(
            id=uuid4(),
            facility_id=room_id,
            name="Day",
            days_of_week_mask=127,
            start_time=time(9, 0),
            end_time=time(12, 0),
            slot_duration_minutes=60,
            is_active=True,
        )
    ]
    first = FileGridItemResult(id=uuid4(), original_name="a.jpg", key="a", storage="s3", bucket="b", region="ca-central-1", url="https://cdn.example/a.jpg")
    second = FileGridItemResult(id=uuid4(), original_name="b.jpg", key="b", storage="s3", bucket="b", region="ca-central-1", url="https://cdn.example/b.jpg")
    service = _make_availability_service(rooms, templates, file_service=StubFileService(files_by_resource={room_id: [first, second]}))
    result = await service.get_rooms_availability(RoomAvailabilityQueryCommand(target_date=date(2026, 7, 20)))
    assert result.items[0].photo_urls == ["https://cdn.example/a.jpg", "https://cdn.example/b.jpg"]
