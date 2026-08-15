"""
Member org API routes.
"""

from dependency_injector.wiring import Provide, inject
from fastapi import Depends, status

from portal.application.locale.locale_service import LocaleService
from portal.application.locale.mappers import locale_list_result_to_api
from portal.application.org.mappers import assignable_positions_to_api
from portal.application.org.position_service import PositionService
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.locale import AdminLocaleList
from portal.serializers.admin.v1.org.position import AdminAssignablePositionList

router: AuthRouter = AuthRouter()


@router.get(path="/positions/assignable", status_code=status.HTTP_200_OK, response_model=AdminAssignablePositionList)
@inject
async def get_assignable_positions(position_service: PositionService = Depends(Provide[Container.org_position_service])):
    result = await position_service.list_assignable()
    return assignable_positions_to_api(result)


@router.get(path="/locales", status_code=status.HTTP_200_OK, response_model=AdminLocaleList, response_model_by_alias=True)
@inject
async def get_locales(locale_service: LocaleService = Depends(Provide[Container.locale_service])):
    result = await locale_service.get_locale_list_result()
    return locale_list_result_to_api(result)
