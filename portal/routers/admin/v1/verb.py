"""
Admin verb API routes
"""

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, status

from portal.application.rbac.mappers import verb_list_result_to_api
from portal.application.rbac.verb_service import VerbService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.verb import AdminVerbList

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/list",
    status_code=status.HTTP_200_OK,
    response_model=AdminVerbList,
    permissions=[
        Permission.SYSTEM_RESOURCE.read
    ]
)
@inject
async def get_verb_list(
    verb_service: VerbService = Depends(Provide[Container.verb_service])
):
    """
    Get verb list
    :param verb_service:
    :return:
    """
    result = await verb_service.get_verb_list()
    return verb_list_result_to_api(result)
