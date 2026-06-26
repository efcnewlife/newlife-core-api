"""
Ministry approval admin API routes.
"""
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.org.mappers import ministry_page_to_api, pages_query_to_command
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins import GenericQueryBaseModel
from portal.serializers.admin.v1.ministry import AdminMinistryPages

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryPages,
    permissions=[Permission.MINISTRY_APPROVAL.read],
)
@inject
async def get_pending_approval_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service]),
):
    result = await approval_service.list_pending_approvals(command=pages_query_to_command(query_model))
    return ministry_page_to_api(result)
