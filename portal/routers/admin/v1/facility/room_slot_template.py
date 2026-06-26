"""
Admin facility room slot template API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.facility.mappers import (
    create_id_result_to_api,
    create_room_slot_template_to_command,
    delete_model_to_command,
    room_slot_template_list_to_api,
    room_slot_template_page_to_api,
    room_slot_template_pages_query_to_command,
    room_slot_template_to_api,
    update_room_slot_template_to_command,
)
from portal.application.facility.room_slot_template_service import RoomSlotTemplateService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.admin.v1.facility.room_slot_template import (
    AdminRoomSlotTemplateCreate,
    AdminRoomSlotTemplateItem,
    AdminRoomSlotTemplateList,
    AdminRoomSlotTemplatePages,
    AdminRoomSlotTemplateQuery,
    AdminRoomSlotTemplateUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomSlotTemplatePages,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.read],
)
@inject
async def get_room_slot_template_pages(
    query_model: Annotated[AdminRoomSlotTemplateQuery, Query()],
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    command, facility_id = room_slot_template_pages_query_to_command(query_model)
    result = await room_slot_template_service.get_template_pages(
        command=command,
        facility_id=facility_id,
    )
    return room_slot_template_page_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomSlotTemplateList,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.read],
)
@inject
async def get_room_slot_template_list(
    facility_id: Annotated[uuid.UUID, Query(alias="facilityId")],
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    result = await room_slot_template_service.get_template_list(facility_id=facility_id)
    return room_slot_template_list_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.create],
)
@inject
async def create_room_slot_template(
    model: AdminRoomSlotTemplateCreate,
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    result = await room_slot_template_service.create_template(
        command=create_room_slot_template_to_command(model)
    )
    return create_id_result_to_api(result)


@router.get(
    path="/{template_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoomSlotTemplateItem,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.read],
)
@inject
async def get_room_slot_template(
    template_id: uuid.UUID,
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    result = await room_slot_template_service.get_template_by_id(template_id=template_id)
    if not result:
        raise HTTPException(status_code=404, detail="Slot template not found")
    return room_slot_template_to_api(result)


@router.put(
    path="/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.modify],
)
@inject
async def update_room_slot_template(
    template_id: uuid.UUID,
    model: AdminRoomSlotTemplateUpdate,
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    await room_slot_template_service.update_template(
        template_id=template_id,
        command=update_room_slot_template_to_command(model),
    )


@router.delete(
    path="/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.delete],
)
@inject
async def delete_room_slot_template(
    template_id: uuid.UUID,
    model: DeleteBaseModel,
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    await room_slot_template_service.delete_template(
        template_id=template_id,
        command=delete_model_to_command(model),
    )


@router.put(
    path="/{template_id}/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.FACILITY_ROOM_SLOT_TEMPLATE.modify],
)
@inject
async def restore_room_slot_template(
    template_id: uuid.UUID,
    room_slot_template_service: RoomSlotTemplateService = Depends(
        Provide[Container.room_slot_template_service]
    ),
):
    await room_slot_template_service.restore_template(template_id=template_id)
