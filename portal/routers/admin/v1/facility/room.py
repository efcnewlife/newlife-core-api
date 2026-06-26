"""
Admin facility room API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.facility.mappers import (
    bulk_action_to_command,
    create_id_result_to_api,
    create_room_to_command,
    delete_model_to_command,
    pages_query_to_command,
    room_detail_to_api,
    room_list_result_to_api,
    room_page_result_to_api,
    update_room_to_command,
)
from portal.application.facility.room_service import RoomService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel, DetailQueryModel, GenericQueryBaseModel
from portal.serializers.admin.v1.facility.room import (
    AdminRoomBulkAction,
    AdminRoomCreate,
    AdminRoomDetail,
    AdminRoomList,
    AdminRoomPages,
    AdminRoomUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomPages,
    permissions=[Permission.FACILITY_ROOM.read],
)
@inject
async def get_room_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    result = await room_service.get_room_pages(command=pages_query_to_command(query_model))
    return room_page_result_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomList,
    permissions=[Permission.FACILITY_ROOM.read],
)
@inject
async def get_room_list(
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    result = await room_service.get_room_list()
    return room_list_result_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_ROOM.create],
)
@inject
async def create_room(
    room_data: AdminRoomCreate,
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    result = await room_service.create_room(command=create_room_to_command(room_data))
    return create_id_result_to_api(result)


@router.get(
    path="/{room_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomDetail,
    permissions=[Permission.FACILITY_ROOM.read],
)
@inject
async def get_room(
    room_id: uuid.UUID,
    query_model: Annotated[DetailQueryModel, Query()],
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    result = await room_service.get_room_by_id(
        room_id=room_id,
        all_locales=query_model.all_locales,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Room not found")
    return room_detail_to_api(result)


@router.put(
    path="/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM.modify],
)
@inject
async def update_room(
    room_id: uuid.UUID,
    room_data: AdminRoomUpdate,
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    await room_service.update_room(room_id=room_id, command=update_room_to_command(room_data))


@router.delete(
    path="/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM.delete],
)
@inject
async def delete_room(
    room_id: uuid.UUID,
    model: DeleteBaseModel,
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    await room_service.delete_room(room_id=room_id, command=delete_model_to_command(model))


@router.put(
    path="/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM.modify],
)
@inject
async def restore_rooms(
    model: AdminRoomBulkAction,
    room_service: RoomService = Depends(Provide[Container.room_service]),
):
    await room_service.restore_rooms(command=bulk_action_to_command(model))
