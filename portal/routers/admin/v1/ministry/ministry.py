"""
Ministry admin API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.org.commands import SubmitMinistryCommand
from portal.application.org.mappers import (
    approve_ministry_to_command,
    bulk_action_to_command,
    create_id_result_to_api,
    create_ministry_to_command,
    delete_model_to_command,
    ministry_detail_to_api,
    ministry_list_to_api,
    ministry_page_to_api,
    pages_query_to_command,
    reject_ministry_to_command,
    replace_ministry_members_to_command,
    update_ministry_to_command,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_service import MinistryService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import DeleteBaseModel, DetailQueryModel, GenericQueryBaseModel
from portal.serializers.admin.v1.ministry import (
    AdminMinistryApprove,
    AdminMinistryBulkAction,
    AdminMinistryCreate,
    AdminMinistryDetail,
    AdminMinistryList,
    AdminMinistryPages,
    AdminMinistryReject,
    AdminMinistryReplaceMembers,
    AdminMinistryUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryPages,
    permissions=[Permission.MINISTRY_MINISTRY.read],
)
@inject
async def get_ministry_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.get_ministry_pages(command=pages_query_to_command(query_model))
    return ministry_page_to_api(result)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryList,
    permissions=[Permission.MINISTRY_MINISTRY.read],
)
@inject
async def get_ministry_list(
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.get_ministry_list()
    return ministry_list_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.MINISTRY_MINISTRY.create],
)
@inject
async def create_ministry(
    model: AdminMinistryCreate,
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.create_ministry(command=create_ministry_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/{ministry_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryDetail,
    permissions=[Permission.MINISTRY_MINISTRY.read],
)
@inject
async def get_ministry(
    ministry_id: uuid.UUID,
    query_model: Annotated[DetailQueryModel, Query()],
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.get_ministry_by_id(
        ministry_id=ministry_id,
        all_locales=query_model.all_locales,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Ministry not found")
    return ministry_detail_to_api(result)


@router.put(
    path="/{ministry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MINISTRY.modify],
)
@inject
async def update_ministry(
    ministry_id: uuid.UUID,
    model: AdminMinistryUpdate,
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    await ministry_service.update_ministry(
        ministry_id=ministry_id,
        command=update_ministry_to_command(model),
    )


@router.delete(
    path="/{ministry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MINISTRY.delete],
)
@inject
async def delete_ministry(
    ministry_id: uuid.UUID,
    model: DeleteBaseModel,
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    await ministry_service.delete_ministry(
        ministry_id=ministry_id,
        command=delete_model_to_command(model),
    )


@router.put(
    path="/restore",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MINISTRY.modify],
)
@inject
async def restore_ministries(
    model: AdminMinistryBulkAction,
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    await ministry_service.restore_ministries(command=bulk_action_to_command(model))


@router.put(
    path="/{ministry_id}/members",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MEMBER.modify],
)
@inject
async def replace_ministry_members(
    ministry_id: uuid.UUID,
    model: AdminMinistryReplaceMembers,
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    await ministry_service.replace_members(
        ministry_id=ministry_id,
        command=replace_ministry_members_to_command(model),
    )


@router.post(
    path="/{ministry_id}/submit",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MINISTRY.modify],
)
@inject
async def submit_ministry(
    ministry_id: uuid.UUID,
    approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service]),
):
    await approval_service.submit_ministry(ministry_id, SubmitMinistryCommand())


@router.post(
    path="/{ministry_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_APPROVAL.modify],
)
@inject
async def approve_ministry(
    ministry_id: uuid.UUID,
    model: AdminMinistryApprove,
    approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service]),
):
    await approval_service.approve_ministry(
        ministry_id=ministry_id,
        command=approve_ministry_to_command(model),
    )


@router.post(
    path="/{ministry_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_APPROVAL.modify],
)
@inject
async def reject_ministry(
    ministry_id: uuid.UUID,
    model: AdminMinistryReject,
    approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service]),
):
    await approval_service.reject_ministry(
        ministry_id=ministry_id,
        command=reject_ministry_to_command(model),
    )
