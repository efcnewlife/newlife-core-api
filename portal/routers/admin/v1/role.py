"""
Admin role API routes
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.rbac.mappers import (
    assign_role_permissions_to_command,
    create_id_result_to_api,
    create_role_to_command,
    delete_model_to_command,
    pages_query_to_command,
    role_detail_result_to_api,
    role_list_result_to_api,
    role_page_result_to_api,
    update_role_to_command,
)
from portal.application.rbac.role_service import RoleService
from portal.container import Container
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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Get paginated roles
    :param query_model:
    :param role_service:
    :return:
    """
    result = await role_service.get_role_pages(command=pages_query_to_command(query_model))
    return role_page_result_to_api(result)


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Get role list
    :param role_service:
    :return:
    """
    result = await role_service.get_active_roles()
    return role_list_result_to_api(result)


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """

    :param role_id:
    :param role_service:
    :return:
    """
    result = await role_service.get_role_by_id(role_id=role_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Role not found")
    return role_detail_result_to_api(result)


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Create a role
    :param role_data:
    :param role_service:
    :return:
    """
    result = await role_service.create_role(command=create_role_to_command(role_data))
    return create_id_result_to_api(result)


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Update a role
    :param role_id:
    :param role_data:
    :param role_service:
    :return:
    """
    await role_service.update_role(role_id=role_id, command=update_role_to_command(role_data))


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Delete a role (soft by default)
    :param role_id:
    :param model:
    :param role_service:
    :return:
    """
    await role_service.delete_role(role_id=role_id, command=delete_model_to_command(model))


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Restore a soft-deleted role
    :param role_id:
    :param role_service:
    :return:
    """
    await role_service.restore_role(role_id=role_id)


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
    role_service: RoleService = Depends(Provide[Container.role_service]),
):
    """
    Assign or revoke permissions for a role
    :param role_id:
    :param model:
    :param role_service:
    :return:
    """
    await role_service.assign_role_permissions(
        role_id=role_id,
        command=assign_role_permissions_to_command(model),
    )
