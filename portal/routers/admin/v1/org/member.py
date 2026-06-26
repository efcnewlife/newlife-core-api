"""
Org member (member.person) admin API routes.
"""
import uuid
from typing import Annotated

from dependency_injector.wiring import inject, Provide
from fastapi import Depends, HTTPException, Query, status

from portal.application.org.mappers import (
    create_id_result_to_api,
    create_member_person_to_command,
    link_member_person_to_command,
    member_person_detail_to_api,
    member_person_page_to_api,
    pages_query_to_command,
    update_member_person_to_command,
)
from portal.application.org.member_person_service import MemberPersonService
from portal.container import Container
from portal.libs.consts.permission import Permission
from portal.routers.auth_router import AuthRouter
from portal.serializers.mixins.model_mixins import UUIDBaseModel
from portal.serializers.mixins import GenericQueryBaseModel
from portal.serializers.admin.v1.org.member_person import (
    AdminMemberPersonCreate,
    AdminMemberPersonDetail,
    AdminMemberPersonLink,
    AdminMemberPersonPages,
    AdminMemberPersonUpdate,
)

router: AuthRouter = AuthRouter(is_admin=True)


@router.get(
    path="/pages",
    status_code=status.HTTP_200_OK,
    response_model=AdminMemberPersonPages,
    permissions=[Permission.MEMBER_PERSON.read],
)
@inject
async def get_member_person_pages(
    query_model: Annotated[GenericQueryBaseModel, Query()],
    member_person_service: MemberPersonService = Depends(Provide[Container.org_member_person_service]),
):
    result = await member_person_service.get_person_pages(command=pages_query_to_command(query_model))
    return member_person_page_to_api(result)


@router.post(
    path="",
    status_code=status.HTTP_201_CREATED,
    response_model=UUIDBaseModel,
    permissions=[Permission.MEMBER_PERSON.create],
)
@inject
async def create_member_person(
    model: AdminMemberPersonCreate,
    member_person_service: MemberPersonService = Depends(Provide[Container.org_member_person_service]),
):
    result = await member_person_service.create_person(command=create_member_person_to_command(model))
    return create_id_result_to_api(result)


@router.get(
    path="/{person_id}",
    status_code=status.HTTP_200_OK,
    response_model=AdminMemberPersonDetail,
    permissions=[Permission.MEMBER_PERSON.read],
)
@inject
async def get_member_person(
    person_id: uuid.UUID,
    member_person_service: MemberPersonService = Depends(Provide[Container.org_member_person_service]),
):
    result = await member_person_service.get_person_by_id(person_id)
    if not result:
        raise HTTPException(status_code=404, detail="Member person not found")
    return member_person_detail_to_api(result)


@router.put(
    path="/{person_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MEMBER_PERSON.modify],
)
@inject
async def update_member_person(
    person_id: uuid.UUID,
    model: AdminMemberPersonUpdate,
    member_person_service: MemberPersonService = Depends(Provide[Container.org_member_person_service]),
):
    await member_person_service.update_person(
        person_id=person_id,
        command=update_member_person_to_command(model),
    )


@router.put(
    path="/{person_id}/link",
    status_code=status.HTTP_204_NO_CONTENT,
    permissions=[Permission.MEMBER_PERSON.modify],
)
@inject
async def link_member_person(
    person_id: uuid.UUID,
    model: AdminMemberPersonLink,
    member_person_service: MemberPersonService = Depends(Provide[Container.org_member_person_service]),
):
    await member_person_service.link_user(
        person_id=person_id,
        command=link_member_person_to_command(model),
    )
