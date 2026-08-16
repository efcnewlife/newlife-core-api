"""
Member ministry API routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.org.mappers import (
    create_id_result_to_api,
    ministry_application_to_command,
    ministry_list_to_api,
    ministry_type_list_to_api,
    target_audience_list_to_api,
)
from portal.application.org.ministry_approval_service import MinistryApprovalService
from portal.application.org.ministry_catalog_service import MinistryCatalogService
from portal.application.org.ministry_service import MinistryService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.ministry import AdminMinistryApplicationCreate, AdminMinistryList
from portal.serializers.admin.v1.ministry_catalog import AdminMinistryTypeList, AdminTargetAudienceList
from portal.serializers.mixins.model_mixins import UUIDBaseModel

router: AuthRouter = AuthRouter()


@router.get(path="/ministries/mine", status_code=status.HTTP_200_OK, response_model=AdminMinistryList)
@inject
async def get_owned_ministries(
    include_pending: bool = Query(False, description="Include pending_approval and rejected ministries"),
    ministry_service: MinistryService = Depends(Provide[Container.org_ministry_service]),
):
    result = await ministry_service.list_owned_ministries(include_pending=include_pending)
    return ministry_list_to_api(result)


@router.post(path="/applications", status_code=status.HTTP_201_CREATED, response_model=UUIDBaseModel)
@inject
async def create_ministry_application(
    model: AdminMinistryApplicationCreate, approval_service: MinistryApprovalService = Depends(Provide[Container.org_ministry_approval_service])
):
    result = await approval_service.create_application(command=ministry_application_to_command(model))
    return create_id_result_to_api(result)


@router.get(path="/catalog/ministry-types", status_code=status.HTTP_200_OK, response_model=AdminMinistryTypeList)
@inject
async def get_ministry_types(catalog_service: MinistryCatalogService = Depends(Provide[Container.org_ministry_catalog_service])):
    result = await catalog_service.list_ministry_types()
    return ministry_type_list_to_api(result)


@router.get(path="/catalog/target-audiences", status_code=status.HTTP_200_OK, response_model=AdminTargetAudienceList)
@inject
async def get_target_audiences(catalog_service: MinistryCatalogService = Depends(Provide[Container.org_ministry_catalog_service])):
    result = await catalog_service.list_target_audiences()
    return target_audience_list_to_api(result)
