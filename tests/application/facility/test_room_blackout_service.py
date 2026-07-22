"""
RoomBlackoutService unit tests.
"""
from datetime import date, time
from uuid import uuid4

import pytest

from portal.application.facility.commands import CreateRoomBlackoutCommand
from portal.application.facility.room_blackout_service import RoomBlackoutService
from portal.application.facility.results import RoomBlackoutResult
from portal.domain.facility.constants import RoomBlackoutKind
from portal.exceptions.responses import BadRequestException, NotFoundException
from tests.fixtures.facility.factories import new_uuid
from tests.fixtures.facility.stubs import StubRoomBlackoutRepository, StubRoomRepository


def _service(blackout_stub, room_ids=None):
    return RoomBlackoutService(
        blackout_stub,
        StubRoomRepository(existing_ids=room_ids or set()),
    )


def _one_off_command(facility_id=None, **overrides):
    payload = dict(
        facility_id=facility_id,
        name="Maintenance",
        reason="HVAC work",
        kind=RoomBlackoutKind.ONE_OFF.value,
        blackout_date=date(2026, 7, 21),
        days_of_week=None,
        start_time=time(9, 0),
        end_time=time(12, 0),
        is_active=True,
    )
    payload.update(overrides)
    return CreateRoomBlackoutCommand(**payload)


def _recurring_command(facility_id=None, **overrides):
    payload = dict(
        facility_id=facility_id,
        name="Weekly closed",
        reason="Staff meeting",
        kind=RoomBlackoutKind.RECURRING.value,
        blackout_date=None,
        days_of_week=[2],
        start_time=time(14, 0),
        end_time=time(16, 0),
        is_active=True,
    )
    payload.update(overrides)
    return CreateRoomBlackoutCommand(**payload)


@pytest.mark.asyncio
async def test_create_one_off_campus_wide():
    stub = StubRoomBlackoutRepository()
    service = _service(stub)
    result = await service.create_blackout(_one_off_command())
    assert result.id
    assert stub.insert_calls[0]["facility_id"] is None
    assert stub.insert_calls[0]["kind"] == RoomBlackoutKind.ONE_OFF.value
    assert stub.insert_calls[0]["days_of_week_mask"] is None


@pytest.mark.asyncio
async def test_create_recurring_encodes_mask():
    facility_id = new_uuid()
    stub = StubRoomBlackoutRepository()
    service = _service(stub, {facility_id})
    await service.create_blackout(_recurring_command(facility_id=facility_id, days_of_week=[0, 2]))
    assert stub.insert_calls[0]["days_of_week_mask"] == (1 << 0) | (1 << 2)
    assert stub.insert_calls[0]["blackout_date"] is None


@pytest.mark.asyncio
async def test_create_rejects_missing_reason():
    service = _service(StubRoomBlackoutRepository())
    with pytest.raises(BadRequestException, match="reason"):
        await service.create_blackout(_one_off_command(reason="  "))


@pytest.mark.asyncio
async def test_create_rejects_invalid_kind_shape():
    service = _service(StubRoomBlackoutRepository())
    with pytest.raises(BadRequestException, match="blackout_date"):
        await service.create_blackout(_one_off_command(blackout_date=None))


@pytest.mark.asyncio
async def test_create_rejects_overlap():
    facility_id = new_uuid()
    existing = RoomBlackoutResult(
        id=uuid4(),
        facility_id=facility_id,
        name="Existing",
        reason="Busy",
        kind=RoomBlackoutKind.ONE_OFF.value,
        blackout_date=date(2026, 7, 21),
        days_of_week_mask=None,
        start_time=time(10, 0),
        end_time=time(11, 0),
        is_active=True,
    )
    stub = StubRoomBlackoutRepository(candidates=[existing])
    service = _service(stub, {facility_id})
    with pytest.raises(BadRequestException, match="overlaps"):
        await service.create_blackout(_one_off_command(facility_id=facility_id))


@pytest.mark.asyncio
async def test_create_room_not_found():
    facility_id = new_uuid()
    service = _service(StubRoomBlackoutRepository(), set())
    with pytest.raises(NotFoundException, match="Room"):
        await service.create_blackout(_one_off_command(facility_id=facility_id))
