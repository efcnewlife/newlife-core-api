"""
Member org API routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, Query, status

from portal.application.locale.locale_service import LocaleService
from portal.application.locale.mappers import locale_list_result_to_api
from portal.application.org.mappers import assignable_positions_to_api, org_user_search_list_to_api, org_user_search_to_command
from portal.application.org.org_user_search_service import OrgUserSearchService
from portal.application.org.position_service import PositionService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.locale import AdminLocaleList
from portal.serializers.admin.v1.org.position import AdminAssignablePositionList
from portal.serializers.apis.v1.org import ApiOrgUserSearchList

router: AuthRouter = AuthRouter()


@router.get(path="/positions/assignable", status_code=status.HTTP_200_OK, response_model=AdminAssignablePositionList)
@inject
async def get_assignable_positions(position_service: PositionService = Depends(Provide[Container.org_position_service])):
    result = await position_service.list_assignable()
    return assignable_positions_to_api(result)


@router.get(path="/users/search", status_code=status.HTTP_200_OK, response_model=ApiOrgUserSearchList, response_model_by_alias=True)
@inject
async def search_users(
    q: str = Query(..., description="Email or display name search"),
    org_user_search_service: OrgUserSearchService = Depends(Provide[Container.org_user_search_service]),
):
    result = await org_user_search_service.search_users(org_user_search_to_command(q))
    return org_user_search_list_to_api(result)


@router.get(path="/locales", status_code=status.HTTP_200_OK, response_model=AdminLocaleList, response_model_by_alias=True)
@inject
async def get_locales(locale_service: LocaleService = Depends(Provide[Container.locale_service])):
    result = await locale_service.get_locale_list_result()
    return locale_list_result_to_api(result)
