"""
Admin booking override audit log API routes.
"""
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.facility.mappers import (
    override_log_page_to_api,
    override_log_pages_query_to_command,
)
from portal.application.facility.override_log_service import OverrideLogService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.override_log import AdminOverrideLogPages, AdminOverrideLogQuery

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminOverrideLogPages,
    permissions=[Permission.FACILITY_BOOKING_OVERRIDE_LOG.read],
)
@inject
async def get_override_log_pages(
    query_model: Annotated[AdminOverrideLogQuery, Query()],
    override_log_service: OverrideLogService = Depends(Provide[Container.override_log_service]),
):
    result = await override_log_service.get_override_log_pages(
        command=override_log_pages_query_to_command(query_model)
    )
    return override_log_page_to_api(result)
