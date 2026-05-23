"""
Admin resource API routes
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status, Query

from portal.application.rbac.mappers import (
    change_resource_parent_to_command,
    change_resource_sequence_to_command,
    create_id_result_to_api,
    create_resource_to_command,
    delete_model_to_command,
    resource_detail_result_to_api,
    resource_list_result_to_api,
    resource_list_query_to_command,
    update_resource_to_command,
)
from portal.application.rbac.resource_service import ResourceService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.admin.v1.resource import (
    AdminResourceCreate,
    AdminResourceUpdate,
    AdminResourceChangeSequence,
    AdminResourceList,
    AdminResourceDetail,
    AdminResourceChangeParent,
)
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.base import DeleteQueryBaseModel

router: AuthRouter = AuthRouter(is_admin=True)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[
        Permission.SYSTEM_RESOURCE.create
    ],
    allow_superuser=True
)
@inject
async def create_resource(
    resource_data: AdminResourceCreate,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_data:
    :param resource_service:
    :return:
    """
    result = await resource_service.create_resource(command=create_resource_to_command(resource_data))
    return create_id_result_to_api(result)


@router.delete(
    path="/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_RESOURCE.delete
    ],
    allow_superuser=True
)
@inject
async def delete_resource(
    resource_id: uuid.UUID,
    model: DeleteBaseModel,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_id:
    :param model:
    :param resource_service:
    :return:
    """
    await resource_service.delete_resource(
        resource_id=resource_id,
        command=delete_model_to_command(model),
    )


@router.put(
    path="/restore/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_RESOURCE.modify
    ],
    allow_superuser=True
)
@inject
async def restore_resource(
    resource_id: uuid.UUID,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_id:
    :param resource_service:
    :return:
    """
    await resource_service.restore_resource(resource_id=resource_id)


@router.put(
    path="/change_parent/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_RESOURCE.modify
    ],
    allow_superuser=True
)
@inject
async def change_resource_parent(
    resource_id: uuid.UUID,
    model: AdminResourceChangeParent,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_id:
    :param model:
    :param resource_service:
    :return:
    """
    await resource_service.change_parent(
        resource_id=resource_id,
        command=change_resource_parent_to_command(model),
    )


@router.put(
    path="/{resource_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_RESOURCE.modify
    ],
    allow_superuser=True
)
@inject
async def update_resource(
    resource_id: uuid.UUID,
    resource_data: AdminResourceUpdate,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_id:
    :param resource_data:
    :param resource_service:
    :return:
    """
    await resource_service.update_resource(
        resource_id=resource_id,
        command=update_resource_to_command(resource_data),
    )


@router.post(
    path="/change_sequence",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_RESOURCE.modify
    ],
    allow_superuser=True
)
@inject
async def change_resource_sequence(
    model: AdminResourceChangeSequence,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param model:
    :param resource_service:
    :return:
    """
    await resource_service.change_sequence(command=change_resource_sequence_to_command(model))


@router.get(
    "/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminResourceList,
    permissions=[
        Permission.SYSTEM_RESOURCE.read
    ]
)
@inject
async def get_resources(
    query_model: Annotated[DeleteQueryBaseModel, Query()],
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """
    Get resources
    :param query_model:
    :param resource_service:
    :return:
    """
    result = await resource_service.get_resources(command=resource_list_query_to_command(query_model))
    return resource_list_result_to_api(result)


@router.get(
    path="/menus",
    status_code=status.HTTP_200_OK,
    response_model=AdminResourceList
)
@inject
async def get_menus(
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """
    Get menus
    :param resource_service:
    :return:
    """
    result = await resource_service.get_user_permission_menus()
    return resource_list_result_to_api(result)


@router.get(
    path="/{resource_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminResourceDetail,
    permissions=[
        Permission.SYSTEM_RESOURCE.read
    ]
)
@inject
async def get_resource(
    resource_id: uuid.UUID,
    resource_service: ResourceService = Depends(Provide[Container.resource_service]),
):
    """

    :param resource_id:
    :param resource_service:
    :return:
    """
    result = await resource_service.get_resource(resource_id=resource_id)
    return resource_detail_result_to_api(result)
