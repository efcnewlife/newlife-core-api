"""
Member ministry approval API routes.
"""

import uuid

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.org.mappers import (
    approve_ministry_to_command,
    ministry_detail_to_api,
    pending_approvals_for_incumbent_to_api,
    reject_ministry_to_command,
    update_rejected_ministry_application_to_command,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.ministry import AdminMinistryDetail
from portal.serializers.apis.v1.ministry import ApiMinistryApprovalPendingList, ApiMinistryApprove, ApiMinistryReject, ApiRejectedMinistryApplicationUpdate

router: AuthRouter = AuthRouter()


@router.get(path="/pending-for-me", status_code=status.HTTP_200_OK, response_model=ApiMinistryApprovalPendingList)
@inject
async def get_pending_approvals_for_incumbent(approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service])):
    result = await approval_service.list_pending_for_incumbent()
    return pending_approvals_for_incumbent_to_api(result)


@router.get(path="/{ministry_id}", status_code=status.HTTP_200_OK, response_model=AdminMinistryDetail)
@inject
async def get_approval_detail(ministry_id: uuid.UUID, approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service])):
    result = await approval_service.get_approval_detail(ministry_id)
    return ministry_detail_to_api(result)


@router.post(path="/{ministry_id}/approve", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def approve_ministry_as_incumbent(
    ministry_id: uuid.UUID, model: ApiMinistryApprove, approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service])
):
    await approval_service.approve_ministry_as_incumbent(ministry_id=ministry_id, command=approve_ministry_to_command(model))


@router.post(path="/{ministry_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reject_ministry_as_incumbent(
    ministry_id: uuid.UUID, model: ApiMinistryReject, approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service])
):
    await approval_service.reject_ministry_as_incumbent(ministry_id=ministry_id, command=reject_ministry_to_command(model))
