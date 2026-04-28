"""
Admin role API routes
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.container import Container
from portal.handlers import AdminRoleHandler
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel, GenericQueryBaseModel
from portal.serializers.admin.v1.role import (
    AdminRolePages,
    AdminRoleCreate,
    AdminRoleUpdate,
    AdminRolePermissionAssign,
    AdminRoleTableItem,
    AdminRoleList,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminRolePages,
    permissions=[
        Permission.SYSTEM_ROLE.read
    ]
)
@inject
async def get_role_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Get paginated roles
    :param query_model:
    :param admin_role_handler:
    :return:
    """
    return await admin_role_handler.get_role_pages(model=query_model)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoleList,
    permissions=[
        Permission.SYSTEM_ROLE.read
    ]
)
@inject
async def get_role_list(
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Get role list
    :param admin_role_handler:
    :return:
    """
    return await admin_role_handler.get_active_roles()


@router.get(
    path="/{role_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminRoleTableItem,
    permissions=[
        Permission.SYSTEM_ROLE.read
    ]
)
@inject
async def get_role(
    role_id: uuid.UUID,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """

    :param role_id:
    :param admin_role_handler:
    :return:
    """
    return await admin_role_handler.get_role_by_id(role_id=role_id)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[
        Permission.SYSTEM_ROLE.create
    ],
    allow_superuser=True
)
@inject
async def create_role(
    role_data: AdminRoleCreate,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Create a role
    :param role_data:
    :param admin_role_handler:
    :return:
    """
    return await admin_role_handler.create_role(model=role_data)


@router.put(
    path="/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_ROLE.modify
    ],
    allow_superuser=True
)
@inject
async def update_role(
    role_id: uuid.UUID,
    role_data: AdminRoleUpdate,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Update a role
    :param role_id:
    :param role_data:
    :param admin_role_handler:
    :return:
    """
    await admin_role_handler.update_role(role_id=role_id, model=role_data)


@router.delete(
    path="/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_ROLE.delete
    ],
    allow_superuser=True
)
@inject
async def delete_role(
    role_id: uuid.UUID,
    model: DeleteBaseModel,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Delete a role (soft by default)
    :param role_id:
    :param model:
    :param admin_role_handler:
    :return:
    """
    await admin_role_handler.delete_role(role_id=role_id, model=model)


@router.put(
    path="/restore/{role_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_ROLE.modify
    ],
    allow_superuser=True
)
@inject
async def restore_role(
    role_id: uuid.UUID,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Restore a soft-deleted role
    :param role_id:
    :param admin_role_handler:
    :return:
    """
    await admin_role_handler.restore_role(role_id=role_id)


@router.post(
    path="/{role_id}/permissions",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_ROLE.modify
    ],
    allow_superuser=True
)
@inject
async def assign_role_permissions(
    role_id: uuid.UUID,
    model: AdminRolePermissionAssign,
    admin_role_handler: AdminRoleHandler = Depends(Provide[Container.admin_role_handler])
):
    """
    Assign or revoke permissions for a role
    :param role_id:
    :param model:
    :param admin_role_handler:
    :return:
    """
    await admin_role_handler.assign_role_permissions(role_id=role_id, model=model)
