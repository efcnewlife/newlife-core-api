"""
RoomService unit tests.
"""

from uuid import uuid4

import pytest

from portal.application.facility.commands import BulkIdsCommand, DeleteCommand, PagesQueryCommand, UpdateRoomCommand
from portal.application.facility.room_service import RoomService
from portal.domain.content.constants import FILE_RESOURCE_KIND_FACILITY_ROOM
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_room_command, make_file_base, make_file_grid_item, make_room_detail, new_uuid
from tests.fixtures.facility.stubs import StubFileService, StubRoomRepository


def make_room_service(room_stub: StubRoomRepository | None = None, file_stub: StubFileService | None = None) -> RoomService:
    return RoomService(room_stub or StubRoomRepository(), file_stub or StubFileService())


@pytest.mark.asyncio
async def test_create_room_success():
    stub = StubRoomRepository()
    service = make_room_service(stub)
    result = await service.create_room(make_create_room_command())
    assert result.id in stub.existing_ids
    assert len(stub.insert_calls) == 1


@pytest.mark.asyncio
async def test_create_room_unique_violation():
    stub = StubRoomRepository(insert_raises_unique=True)
    service = make_room_service(stub)
    with pytest.raises(ConflictErrorException, match="Room code") as exc_info:
        await service.create_room(make_create_room_command())
    assert exc_info.value.error_code == "FACILITY_ROOM_CODE_EXISTS"


@pytest.mark.asyncio
async def test_update_room_not_found():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={})
    service = make_room_service(stub)

    with pytest.raises(NotFoundException, match="Room") as exc_info:
        await service.update_room(room_id, UpdateRoomCommand(is_active=True))
    assert exc_info.value.error_code == "FACILITY_ROOM_NOT_FOUND"
    assert exc_info.value.context == {"room_id": str(room_id)}


@pytest.mark.asyncio
async def test_delete_room_not_found():
    service = make_room_service()
    with pytest.raises(NotFoundException):
        await service.delete_room(uuid4(), DeleteCommand(reason="x", permanent=False))


@pytest.mark.asyncio
async def test_restore_rooms_empty_ids():
    service = make_room_service()
    with pytest.raises(BadRequestException, match="No room ids"):
        await service.restore_rooms(BulkIdsCommand(ids=[]))


@pytest.mark.asyncio
async def test_delete_room_soft_when_not_permanent():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={room_id: make_room_detail(room_id)})
    file_stub = StubFileService()
    service = make_room_service(stub, file_stub)
    await service.delete_room(room_id, DeleteCommand(reason="cleanup", permanent=False))
    assert room_id in stub.room_by_id
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_create_room_replaces_gallery_in_list_order():
    first_file = make_file_base()
    second_file = make_file_base()
    file_stub = StubFileService(active_files={first_file.id: first_file, second_file.id: second_file})
    service = make_room_service(file_stub=file_stub)
    result = await service.create_room(make_create_room_command(file_ids=[second_file.id, first_file.id]))
    assert len(file_stub.association_commands) == 1
    command = file_stub.association_commands[0]
    assert command.resource_id == result.id
    assert command.resource_name == FILE_RESOURCE_KIND_FACILITY_ROOM
    assert command.file_ids == [second_file.id, first_file.id]


@pytest.mark.asyncio
async def test_create_room_omitted_file_ids_does_not_replace_gallery():
    file_stub = StubFileService()
    service = make_room_service(file_stub=file_stub)
    await service.create_room(make_create_room_command())
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_update_room_empty_file_ids_clears_gallery():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={room_id: make_room_detail(room_id)})
    file_stub = StubFileService()
    service = make_room_service(stub, file_stub)
    await service.update_room(room_id, UpdateRoomCommand(is_active=True, file_ids=[]))
    assert len(file_stub.association_commands) == 1
    assert file_stub.association_commands[0].file_ids == []
    assert file_stub.association_commands[0].resource_name == FILE_RESOURCE_KIND_FACILITY_ROOM


@pytest.mark.asyncio
async def test_update_room_omitted_file_ids_leaves_gallery():
    room_id = new_uuid()
    stub = StubRoomRepository(room_by_id={room_id: make_room_detail(room_id)})
    file_stub = StubFileService()
    service = make_room_service(stub, file_stub)
    await service.update_room(room_id, UpdateRoomCommand(is_active=True))
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_get_room_by_id_includes_gallery_files_in_sequence():
    room_id = new_uuid()
    files = [make_file_grid_item(url="https://signed.example/a.jpg"), make_file_grid_item(url="https://signed.example/b.jpg")]
    stub = StubRoomRepository(room_by_id={room_id: make_room_detail(room_id)})
    file_stub = StubFileService(files_by_resource={room_id: files})
    service = make_room_service(stub, file_stub)
    result = await service.get_room_by_id(room_id)
    assert result is not None
    assert [item.id for item in result.files] == [files[0].id, files[1].id]
    assert [item.url for item in result.files] == ["https://signed.example/a.jpg", "https://signed.example/b.jpg"]


@pytest.mark.asyncio
async def test_get_room_pages_omits_gallery_files():
    stub = StubRoomRepository()
    file_stub = StubFileService()
    service = make_room_service(stub, file_stub)
    result = await service.get_room_pages(PagesQueryCommand(page=0, page_size=10))
    assert result.items == []
    assert file_stub.get_files_calls == []


@pytest.mark.asyncio
async def test_create_room_rejects_more_than_ten_gallery_files():
    files = [make_file_base() for _ in range(11)]
    file_stub = StubFileService(active_files={item.id: item for item in files})
    service = make_room_service(file_stub=file_stub)
    with pytest.raises(BadRequestException, match="10"):
        await service.create_room(make_create_room_command(file_ids=[item.id for item in files]))
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_create_room_rejects_duplicate_gallery_file_ids():
    file_item = make_file_base()
    file_stub = StubFileService(active_files={file_item.id: file_item})
    service = make_room_service(file_stub=file_stub)
    with pytest.raises(BadRequestException, match="unique"):
        await service.create_room(make_create_room_command(file_ids=[file_item.id, file_item.id]))
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_create_room_rejects_missing_or_deleted_gallery_file_ids():
    file_item = make_file_base()
    missing_id = new_uuid()
    file_stub = StubFileService(active_files={file_item.id: file_item})
    service = make_room_service(file_stub=file_stub)
    with pytest.raises(BadRequestException, match="not found"):
        await service.create_room(make_create_room_command(file_ids=[file_item.id, missing_id]))
    assert file_stub.association_commands == []


@pytest.mark.asyncio
async def test_create_room_rejects_non_image_gallery_files():
    file_item = make_file_base(content_type="application/pdf")
    file_stub = StubFileService(active_files={file_item.id: file_item})
    service = make_room_service(file_stub=file_stub)
    with pytest.raises(BadRequestException, match="image"):
        await service.create_room(make_create_room_command(file_ids=[file_item.id]))
    assert file_stub.association_commands == []
