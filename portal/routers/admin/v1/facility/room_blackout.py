"""
Admin facility room blackout API routes.
"""

import uuid
from typing import Annotated, Optional

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, HTTPException, Query, status

from portal.application.facility.mappers import (
    create_id_result_to_api,
    create_room_blackout_to_command,
    delete_model_to_command,
    room_blackout_list_to_api,
    room_blackout_page_to_api,
    room_blackout_pages_query_to_command,
    room_blackout_to_api,
    update_room_blackout_to_command,
)
from portal.application.facility.room_blackout_service import RoomBlackoutService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.room_blackout import (
    AdminRoomBlackoutCreate,
    AdminRoomBlackoutItem,
    AdminRoomBlackoutList,
    AdminRoomBlackoutPages,
    AdminRoomBlackoutQuery,
    AdminRoomBlackoutUpdate,
)
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(path="/pages", status_code=status.HTTP_200_OK, response_model=AdminRoomBlackoutPages, permissions=[Permission.FACILITY_ROOM_BLACKOUT.read])
@inject
async def get_room_blackout_pages(
    query_model: Annotated[AdminRoomBlackoutQuery, Query()], room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])
):
    command, facility_id = room_blackout_pages_query_to_command(query_model)
    result = await room_blackout_service.get_blackout_pages(command=command, facility_id=facility_id)
    return room_blackout_page_to_api(result)


@router.get(path="/list", status_code=status.HTTP_200_OK, response_model=AdminRoomBlackoutList, permissions=[Permission.FACILITY_ROOM_BLACKOUT.read])
@inject
async def get_room_blackout_list(
    facility_id: Annotated[Optional[uuid.UUID], Query(alias="facilityId")] = None,
    room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service]),
):
    result = await room_blackout_service.get_blackout_list(facility_id=facility_id)
    return room_blackout_list_to_api(result)


@router.post(path="", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel, permissions=[Permission.FACILITY_ROOM_BLACKOUT.create])
@inject
async def create_room_blackout(model: AdminRoomBlackoutCreate, room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])):
    result = await room_blackout_service.create_blackout(command=create_room_blackout_to_command(model))
    return create_id_result_to_api(result)


@router.get(path="/{blackout_id}", status_code=status.HTTP_200_OK, response_model=AdminRoomBlackoutItem, permissions=[Permission.FACILITY_ROOM_BLACKOUT.read])
@inject
async def get_room_blackout(blackout_id: uuid.UUID, room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])):
    result = await room_blackout_service.get_blackout_by_id(blackout_id=blackout_id)
    if not result:
        raise HTTPException(status_code=404, detail="Blackout not found")
    return room_blackout_to_api(result)


@router.put(path="/{blackout_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_ROOM_BLACKOUT.modify])
@inject
async def update_room_blackout(
    blackout_id: uuid.UUID, model: AdminRoomBlackoutUpdate, room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])
):
    await room_blackout_service.update_blackout(blackout_id=blackout_id, command=update_room_blackout_to_command(model))


@router.delete(path="/{blackout_id}", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_ROOM_BLACKOUT.delete])
@inject
async def delete_room_blackout(
    blackout_id: uuid.UUID, model: DeleteBaseModel, room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])
):
    await room_blackout_service.delete_blackout(blackout_id=blackout_id, command=delete_model_to_command(model))


@router.put(path="/{blackout_id}/restore", status_code=status.HTTP_204_NO_CONTENT, permissions=[Permission.FACILITY_ROOM_BLACKOUT.modify])
@inject
async def restore_room_blackout(blackout_id: uuid.UUID, room_blackout_service: RoomBlackoutService = Depends(Provide[Container.room_blackout_service])):
    await room_blackout_service.restore_blackout(blackout_id=blackout_id)
