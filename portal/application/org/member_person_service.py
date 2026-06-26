"""
Member person application service.
"""
import uuid
from typing import Optional
from uuid import UUID

from portal.application.org.commands import (
    CreateMemberPersonCommand,
    LinkMemberPersonCommand,
    PagesQueryCommand,
    UpdateMemberPersonCommand,
)
from portal.application.org.results import CreateIdResult, MemberPersonDetailResult, MemberPersonPageResult
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.infrastructure.persistence.repositories.member.person_repository import PersonRepository
from portal.libs.tracing.distributed_trace import distributed_trace


class MemberPersonService:
    """Member person record and user linking."""

    def __init__(self, person_repository: PersonRepository):
        self._repository = person_repository

    @distributed_trace()
    async def get_person_pages(self, command: PagesQueryCommand) -> MemberPersonPageResult:
        items, count = await self._repository.fetch_pages(command)
        return MemberPersonPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_person_by_id(self, person_id: UUID) -> MemberPersonDetailResult:
        row = await self._repository.get_by_id(person_id)
        if not row:
            raise NotFoundException(detail=f"Member person {person_id} not found")
        return row

    @distributed_trace()
    async def create_person(self, command: CreateMemberPersonCommand) -> CreateIdResult:
        person_id = uuid.uuid4()
        await self._repository.insert_person(
            dict(
                id=person_id,
                legal_name=command.legal_name,
                user_id=command.user_id,
            )
        )
        return CreateIdResult(id=person_id)

    @distributed_trace()
    async def update_person(self, person_id: UUID, command: UpdateMemberPersonCommand) -> None:
        if not await self._repository.get_by_id(person_id):
            raise NotFoundException(detail=f"Member person {person_id} not found")
        affected = await self._repository.update_person(
            person_id,
            dict(legal_name=command.legal_name),
        )
        if affected == 0:
            raise NotFoundException(detail=f"Member person {person_id} not found")

    @distributed_trace()
    async def link_user(self, person_id: UUID, command: LinkMemberPersonCommand) -> None:
        if not await self._repository.get_by_id(person_id):
            raise NotFoundException(detail=f"Member person {person_id} not found")
        if await self._repository.user_already_linked(command.user_id, exclude_person_id=person_id):
            raise BadRequestException(detail="User is already linked to another member person")
        affected = await self._repository.link_user(person_id, command.user_id)
        if affected == 0:
            raise NotFoundException(detail=f"Member person {person_id} not found")
