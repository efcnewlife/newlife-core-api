"""
Admin facility member API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, Query, status

from portal.application.facility.member_service import MemberService
from portal.application.facility.mappers import (
    member_detail_to_api,
    member_page_to_api,
    member_pages_query_to_command,
    replace_member_ministries_to_command,
)
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.admin.v1.facility.member import (
    AdminMemberDetail,
    AdminMemberMinistriesUpdate,
    AdminMemberPages,
    AdminMemberQuery,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminMemberPages,
    permissions=[Permission.FACILITY_MEMBER.read],
)
@inject
async def get_member_pages(
    query_model: Annotated[AdminMemberQuery, Query()],
    member_service: MemberService = Depends(Provide[Container.member_service]),
):
    result = await member_service.get_member_pages(command=member_pages_query_to_command(query_model))
    return member_page_to_api(result)


@router.get(
    path="/{user_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminMemberDetail,
    permissions=[Permission.FACILITY_MEMBER.read],
)
@inject
async def get_member_detail(
    user_id: uuid.UUID,
    member_service: MemberService = Depends(Provide[Container.member_service]),
):
    result = await member_service.get_member_by_id(user_id)
    return member_detail_to_api(result)


@router.put(
    path="/{user_id}/ministries",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MINISTRY_MEMBER.modify],
)
@inject
async def replace_member_ministries(
    user_id: uuid.UUID,
    body: AdminMemberMinistriesUpdate,
    member_service: MemberService = Depends(Provide[Container.member_service]),
):
    await member_service.replace_user_ministries(
        user_id=user_id,
        command=replace_member_ministries_to_command(body),
    )
