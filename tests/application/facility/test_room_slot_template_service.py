"""
RoomSlotTemplateService unit tests.
"""
from datetime import time
from uuid import uuid4

import pytest

from portal.application.facility.room_slot_template_service import RoomSlotTemplateService
from portal.exceptions.responses import BadRequestException, NotFoundException
from tests.fixtures.facility.factories import (
    make_create_slot_template_command,
    make_slot_template_result,
    new_uuid,
)
from tests.fixtures.facility.stubs import StubRoomRepository, StubRoomSlotTemplateRepository


def _service(template_stub, room_ids=None):
    return RoomSlotTemplateService(
        template_stub,
        StubRoomRepository(existing_ids=room_ids or set()),
    )


@pytest.mark.asyncio
async def test_create_template_rejects_invalid_time_window():
    facility_id = new_uuid()
    command = make_create_slot_template_command(facility_id, start_time=time(12, 0), end_time=time(9, 0))
    service = _service(StubRoomSlotTemplateRepository(), {facility_id})
    with pytest.raises(BadRequestException, match="start_time"):
        await service.create_template(command)


@pytest.mark.asyncio
async def test_create_template_rejects_non_positive_duration():
    facility_id = new_uuid()
    command = make_create_slot_template_command(facility_id)
    command.slot_duration_minutes = 0
    service = _service(StubRoomSlotTemplateRepository(), {facility_id})
    with pytest.raises(BadRequestException, match="slot_duration_minutes"):
        await service.create_template(command)


@pytest.mark.asyncio
async def test_create_template_rejects_overlap():
    facility_id = new_uuid()
    candidate = make_slot_template_result(facility_id, days_of_week_mask=4, start_time=time(9, 0), end_time=time(12, 0))
    command = make_create_slot_template_command(
        facility_id,
        start_time=time(10, 0),
        end_time=time(11, 0),
        days_of_week=[2],
    )
    service = _service(StubRoomSlotTemplateRepository(candidates=[candidate]), {facility_id})
    with pytest.raises(BadRequestException, match="overlaps"):
        await service.create_template(command)


@pytest.mark.asyncio
async def test_create_template_no_overlap_on_different_weekdays():
    facility_id = new_uuid()
    candidate = make_slot_template_result(facility_id, days_of_week_mask=1, start_time=time(9, 0), end_time=time(12, 0))
    command = make_create_slot_template_command(
        facility_id,
        start_time=time(10, 0),
        end_time=time(11, 0),
        days_of_week=[1],
    )
    template_stub = StubRoomSlotTemplateRepository(candidates=[candidate])
    service = _service(template_stub, {facility_id})
    result = await service.create_template(command)
    assert result.id is not None
    assert template_stub.insert_calls[0]["days_of_week_mask"] == 2


@pytest.mark.asyncio
async def test_create_template_stores_days_mask():
    facility_id = new_uuid()
    command = make_create_slot_template_command(facility_id, days_of_week=[0, 1, 2, 3, 4])
    template_stub = StubRoomSlotTemplateRepository()
    service = _service(template_stub, {facility_id})
    await service.create_template(command)
    assert template_stub.insert_calls[0]["days_of_week_mask"] == 31


@pytest.mark.asyncio
async def test_create_template_inactive_skips_overlap_check():
    facility_id = new_uuid()
    candidate = make_slot_template_result(facility_id)
    template_stub = StubRoomSlotTemplateRepository(candidates=[candidate])
    command = make_create_slot_template_command(facility_id, is_active=False)
    service = _service(template_stub, {facility_id})
    result = await service.create_template(command)
    assert template_stub.list_candidates_calls == 0
    assert result.id is not None


@pytest.mark.asyncio
async def test_update_template_not_found():
    facility_id = new_uuid()
    command = make_create_slot_template_command(facility_id)
    service = _service(StubRoomSlotTemplateRepository(), {facility_id})
    with pytest.raises(NotFoundException, match="Slot template"):
        await service.update_template(uuid4(), command)


@pytest.mark.asyncio
async def test_create_template_room_not_found():
    facility_id = new_uuid()
    service = _service(StubRoomSlotTemplateRepository())
    with pytest.raises(NotFoundException, match="Room"):
        await service.create_template(make_create_slot_template_command(facility_id))
