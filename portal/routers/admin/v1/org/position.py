"""
Org position admin API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.org.mappers import (
    assign_position_to_command,
    assignable_positions_to_api,
    bulk_action_to_command,
    create_id_result_to_api,
    create_position_to_command,
    delete_model_to_command,
    pages_query_to_command,
    position_detail_to_api,
    position_page_to_api,
    update_position_to_command,
)
from portal.application.org.position_service import PositionService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel, DetailQueryModel, GenericQueryBaseModel
from portal.serializers.admin.v1.org.position import (
    AdminAssignablePositionList,
    AdminPositionAssign,
    AdminPositionBulkAction,
    AdminPositionCreate,
    AdminPositionDetail,
    AdminPositionPages,
    AdminPositionUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminPositionPages,
    permissions=[Permission.ORG_POSITION.read],
)
@inject
async def get_position_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    result = await position_service.get_position_pages(command=pages_query_to_command(query_model))
    return position_page_to_api(result)


@router.get(
    path="/assignable",
    status_code=status.HTTP_200_OK,
    response_model=AdminAssignablePositionList,
    permissions=[Permission.ORG_POSITION.read],
)
@inject
async def get_assignable_positions(
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    result = await position_service.list_assignable()
    return assignable_positions_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.ORG_POSITION.create],
)
@inject
async def create_position(
    model: AdminPositionCreate,
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    result = await position_service.create_position(command=create_position_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/{position_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminPositionDetail,
    permissions=[Permission.ORG_POSITION.read],
)
@inject
async def get_position(
    position_id: uuid.UUID,
    query_model: Annotated[DetailQueryModel, Query()],
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    result = await position_service.get_position_by_id(
        position_id=position_id,
        all_locales=query_model.all_locales,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Position not found")
    return position_detail_to_api(result)


@router.put(
    path="/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.ORG_POSITION.modify],
)
@inject
async def update_position(
    position_id: uuid.UUID,
    model: AdminPositionUpdate,
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    await position_service.update_position(
        position_id=position_id,
        command=update_position_to_command(model),
    )


@router.delete(
    path="/{position_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.ORG_POSITION.delete],
)
@inject
async def delete_position(
    position_id: uuid.UUID,
    model: DeleteBaseModel,
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    await position_service.delete_position(
        position_id=position_id,
        command=delete_model_to_command(model),
    )


@router.put(
    path="/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.ORG_POSITION.modify],
)
@inject
async def restore_positions(
    model: AdminPositionBulkAction,
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    await position_service.restore_positions(command=bulk_action_to_command(model))


@router.put(
    path="/{position_id}/assign",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.ORG_POSITION.modify],
)
@inject
async def assign_position(
    position_id: uuid.UUID,
    model: AdminPositionAssign,
    position_service: PositionService = Depends(Provide[Container.org_position_service]),
):
    await position_service.assign_position(
        position_id=position_id,
        command=assign_position_to_command(model),
    )
