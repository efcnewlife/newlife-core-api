"""
Member ministry API routes.
"""
from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status

from portal.application.org.mappers import (
    create_id_result_to_api,
    ministry_application_to_command,
    ministry_list_to_api,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_service import MinistryService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.admin.v1.ministry import AdminMinistryApplicationCreate, AdminMinistryList

router: AuthRouter = AuthRouter()


@router.get(
    path="/ministries/mine",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryList,
)
@inject
async def get_owned_ministries(
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.list_owned_ministries()
    return ministry_list_to_api(result)


@router.post(
    path="/applications",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
)
@inject
async def create_ministry_application(
    model: AdminMinistryApplicationCreate,
    approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service]),
):
    result = await approval_service.create_application(command=ministry_application_to_command(model))
    return create_id_result_to_api(result)
