"""
Admin user API routes
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.rbac.mappers import (
    admin_user_detail_result_to_api,
    admin_user_list_result_to_api,
    admin_user_page_result_to_api,
    admin_user_roles_result_to_api,
    admin_user_pages_query_to_command,
    bind_user_roles_to_command,
    bulk_ids_to_command,
    change_password_to_command,
    create_admin_user_to_command,
    create_id_result_to_api,
    delete_model_to_command,
    update_admin_user_to_command,
)
from portal.container import Container
from portal.application.auth.admin_user_service import AdminUserService
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel
from portal.serializers.mixins.base import KeywordQueryBaseModel
from portal.serializers.admin.v1.user import (
    AdminUserQuery,
    AdminUserPages,
    AdminUserCreate,
    AdminUserItem,
    AdminUserUpdate,
    AdminUserBulkAction,
    AdminBindRole,
    AdminChangePassword,
    AdminUserRoles,
    AdminUserList,
    AdminUserPreferredLanguageUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminUserPages,
    permissions=[
        Permission.SYSTEM_USER.read
    ]
)
@inject
async def get_user_pages(
    query_model: Annotated[AdminUserQuery, Query()],
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Get user pages
    :param query_model:
    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.get_user_pages(command=admin_user_pages_query_to_command(query_model))
    return admin_user_page_result_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminUserList,
    permissions=[
        Permission.SYSTEM_USER.read
    ]
)
@inject
async def get_user_list(
    query_model: Annotated[KeywordQueryBaseModel, Query()],
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """

    :param query_model:
    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.get_user_list(keyword=query_model.keyword)
    return admin_user_list_result_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[
        Permission.SYSTEM_USER.create
    ]
)
@inject
async def create_user(
    user_data: AdminUserCreate,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Create a user
    :param user_data:
    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.create_user(command=create_admin_user_to_command(user_data))
    return create_id_result_to_api(result)


@router.get(
    path="/me",
    status_code=status.HTTP_200_OK,
    response_model=AdminUserItem,
)
@inject
async def get_current_user(
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """

    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.get_current_user()
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return admin_user_detail_result_to_api(result)


@router.put(
    path="/me",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def update_current_user(
    user_data: AdminUserUpdate,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """

    :param user_data:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.update_current_user(command=update_admin_user_to_command(user_data))


@router.put(
    path="/me/preferred-language",
    status_code=status.HTTP_204_NO_CONTENT,
)
@inject
async def update_current_user_preferred_locale(
    model: AdminUserPreferredLanguageUpdate,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Update current user preferred locale.
    """
    await admin_user_service.update_current_user_preferred_locale(model.preferred_locale_id)


@router.get(
    path="/{user_id}/roles",
    status_code=status.HTTP_200_OK,
    description="Get user roles",
    response_model=AdminUserRoles,
    permissions=[
        Permission.SYSTEM_USER.read
    ]
)
@inject
async def get_user_roles(
    user_id: uuid.UUID,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Get user roles
    :param user_id:
    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.get_user_roles(user_id=user_id)
    return admin_user_roles_result_to_api(result)


@router.get(
    path="/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminUserItem,
    permissions=[
        Permission.SYSTEM_USER.read
    ]
)
@inject
async def get_user(
    user_id: uuid.UUID,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Get a user by ID
    :param user_id:
    :param admin_user_service:
    :return:
    """
    result = await admin_user_service.get_user_by_id(user_id=user_id)
    if not result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    return admin_user_detail_result_to_api(result)


@router.put(
    path="/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_USER.modify
    ]
)
@inject
async def restore_users(
    model: AdminUserBulkAction,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Restore soft-deleted users
    :param model:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.restore_user(command=bulk_ids_to_command(model))


@router.post(
    path="/{user_id}/bind_role",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_USER.modify
    ],
    allow_superuser=True
)
@inject
async def bind_roles_to_user(
    user_id: uuid.UUID,
    model: AdminBindRole,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Bind roles to user
    :param user_id:
    :param model:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.bind_roles(
        user_id=user_id,
        command=bind_user_roles_to_command(model),
    )


@router.post(
    path="/{user_id}/change_password",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_USER.modify
    ]
)
@inject
async def change_user_password(
    user_id: uuid.UUID,
    model: AdminChangePassword,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """

    :param user_id:
    :param model:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.change_password(
        user_id=user_id,
        command=change_password_to_command(model),
    )


@router.put(
    path="/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_USER.modify
    ]
)
@inject
async def update_user(
    user_id: uuid.UUID,
    user_data: AdminUserUpdate,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Update a user
    :param user_id:
    :param user_data:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.update_user(
        user_id=user_id,
        command=update_admin_user_to_command(user_data),
    )


@router.delete(
    path="/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[
        Permission.SYSTEM_USER.delete
    ]
)
@inject
async def delete_user(
    user_id: uuid.UUID,
    model: DeleteBaseModel,
    admin_user_service: AdminUserService = Depends(Provide[Container.admin_user_service])
):
    """
    Delete a user (soft by default)
    :param user_id:
    :param model:
    :param admin_user_service:
    :return:
    """
    await admin_user_service.delete_user(
        user_id=user_id,
        command=delete_model_to_command(model),
    )
