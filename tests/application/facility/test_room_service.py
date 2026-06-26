"""
RoomService unit tests.
"""
from uuid import uuid4

import pytest

from portal.application.facility.commands import BulkIdsCommand, DeleteCommand
from portal.application.facility.room_service import RoomService
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_room_command, make_room_detail, new_uuid
from tests.fixtures.facility.stubs import StubRoomRepository


@pytest.mark.asyncio
async def test_create_room_success():
    stub = StubRoomRepository()
    service = RoomService(stub)
    result = await service.create_room(make_create_room_command())
    assert result.id in stub.existing_ids
    assert len(stub.insert_calls) == 1


@pytest.mark.asyncio
async def test_create_room_unique_violation():
    stub = StubRoomRepository(insert_raises_unique=True)
    service = RoomService(stub)
    with pytest.raises(ConflictErrorException, match="Room code"):
        await service.create_room(make_create_room_command())


@pytest.mark.asyncio
async def test_update_room_not_found():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={})
    service = RoomService(stub)
    from portal.application.facility.commands import UpdateRoomCommand

    with pytest.raises(NotFoundException, match="Room"):
        await service.update_room(room_id, UpdateRoomCommand(is_active=True))


@pytest.mark.asyncio
async def test_delete_room_not_found():
    service = RoomService(StubRoomRepository())
    with pytest.raises(NotFoundException):
        await service.delete_room(uuid4(), DeleteCommand(reason="x", permanent=False))


@pytest.mark.asyncio
async def test_restore_rooms_empty_ids():
    service = RoomService(StubRoomRepository())
    with pytest.raises(BadRequestException, match="No room ids"):
        await service.restore_rooms(BulkIdsCommand(ids=[]))


@pytest.mark.asyncio
async def test_delete_room_soft_when_not_permanent():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={room_id: make_room_detail(room_id)})
    service = RoomService(stub)
    await service.delete_room(room_id, DeleteCommand(reason="cleanup", permanent=False))
    assert room_id in stub.room_by_id
