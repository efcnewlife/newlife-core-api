"""
Admin permission API routes
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status, Query

from portal.application.rbac.mappers import (
    create_id_result_to_api,
    create_permission_to_command,
    delete_model_to_command,
    permission_bulk_action_to_command,
    permission_detail_result_to_api,
    permission_list_result_to_api,
    permission_page_result_to_api,
    permission_pages_query_to_command,
    update_permission_to_command,
)
from portal.application.rbac.permission_service import PermissionService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.admin.v1.permission import (
    AdminPermissionPage,
    AdminPermissionQuery,
    AdminPermissionDetail,
    AdminPermissionCreate,
    AdminPermissionUpdate,
    AdminPermissionBulkAction,
    AdminPermissionList,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminPermissionPage,
    permissions=[
        Permission.SYSTEM_PERMISSION.read
    ]
)
@inject
async def get_permission_pages(
    query_model: Annotated[AdminPermissionQuery, Query()],
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Get permission pages
    :param query_model:
    :param permission_service:
    :return:
    """
    result = await permission_service.get_permission_pages(
        command=permission_pages_query_to_command(query_model),
    )
    return permission_page_result_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminPermissionList,
    permissions=[
        Permission.SYSTEM_PERMISSION.read
    ]
)
@inject
async def get_permission_list(
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """

    :param permission_service:
    :return:
    """
    result = await permission_service.get_permission_list()
    return permission_list_result_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[
        Permission.SYSTEM_PERMISSION.create
    ],
    allow_superuser=True
)
@inject
async def create_permission(
    permission_data: AdminPermissionCreate,
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Create a permission
    :param permission_data:
    :param permission_service:
    :return:
    """
    result = await permission_service.create_permission(
        command=create_permission_to_command(permission_data),
    )
    return create_id_result_to_api(result)


@router.get(
    path="/{permission_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminPermissionDetail,
    permissions=[
        Permission.SYSTEM_PERMISSION.read
    ]
)
@inject
async def get_permission(
    permission_id: uuid.UUID,
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Get a permission by ID
    :param permission_id:
    :param permission_service:
    :return:
    """
    result = await permission_service.get_permission_by_id(permission_id=permission_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission_detail_result_to_api(result)


@router.put(
    path="/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_PERMISSION.modify
    ],
    allow_superuser=True
)
@inject
async def restore_permission(
    model: AdminPermissionBulkAction,
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Restore a permission
    :param model:
    :param permission_service:
    :return:
    """
    await permission_service.restore_permission(
        command=permission_bulk_action_to_command(model),
    )


@router.put(
    path="/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_PERMISSION.modify
    ],
    allow_superuser=True
)
@inject
async def update_permission(
    permission_id: uuid.UUID,
    permission_data: AdminPermissionUpdate,
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Update a permission
    :param permission_id:
    :param permission_data:
    :param permission_service:
    :return:
    """
    await permission_service.update_permission(
        permission_id=permission_id,
        command=update_permission_to_command(permission_data),
    )


@router.delete(
    path="/{permission_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_PERMISSION.delete
    ],
    allow_superuser=True
)
@inject
async def delete_permission(
    permission_id: uuid.UUID,
    model: DeleteBaseModel,
    permission_service: PermissionService = Depends(Provide[Container.permission_service]),
):
    """
    Delete a permission
    :param permission_id:
    :param model:
    :param permission_service:
    :return:
    """
    await permission_service.delete_permission(
        permission_id=permission_id,
        command=delete_model_to_command(model),
    )
