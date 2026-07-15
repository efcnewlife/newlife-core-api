"""
Ministry catalog admin API routes.
"""
from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status

from portal.application.org.mappers import ministry_type_list_to_api, target_audience_list_to_api
from portal.application.org.ministry_catalog_service import MinistryCatalogService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.ministry_catalog import AdminMinistryTypeList, AdminTargetAudienceList

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/ministry-types",
    status_code=status.HTTP_200_OK,
    response_model=AdminMinistryTypeList,
    permissions=[Permission.MINISTRY_MINISTRY.read],
)
@inject
async def get_ministry_types(
    catalog_service: MinistryCatalogService = Depends(Provide[Container.org_ministry_catalog_service]),
):
    result = await catalog_service.list_ministry_types()
    return ministry_type_list_to_api(result)


@router.get(
    path="/target-audiences",
    status_code=status.HTTP_200_OK,
    response_model=AdminTargetAudienceList,
    permissions=[Permission.MINISTRY_MINISTRY.read],
)
@inject
async def get_target_audiences(
    catalog_service: MinistryCatalogService = Depends(Provide[Container.org_ministry_catalog_service]),
):
    result = await catalog_service.list_target_audiences()
    return target_audience_list_to_api(result)
