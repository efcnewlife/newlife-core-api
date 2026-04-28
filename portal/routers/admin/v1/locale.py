"""
Admin locale API routes
"""

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status

from portal.container import Container
from portal.handlers import AdminLocaleHandler
from portal.libs.consts.permission import Permission
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
    admin_locale_handler: AdminLocaleHandler = Depends(Provide[Container.admin_locale_handler])
) -> AdminLocaleList:
    """
    Get verb list
    :param admin_locale_handler:
    :return:
    """
    return await admin_locale_handler.get_locale_list()
