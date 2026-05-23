"""
Admin locale API routes
"""

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status

from portal.application.locale.locale_service import LocaleService
from portal.application.locale.mappers import locale_list_result_to_api
from portal.container import Container
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.locale import AdminLocaleList


router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminLocaleList,
    # TODO: Set permissions
    # permissions=
)
@inject
async def get_locale_list(
    locale_service: LocaleService = Depends(Provide[Container.locale_service]),
) -> AdminLocaleList:
    """
    Get locale list
    :param locale_service:
    :return:
    """
    result = await locale_service.get_locale_list_result()
    return locale_list_result_to_api(result)
