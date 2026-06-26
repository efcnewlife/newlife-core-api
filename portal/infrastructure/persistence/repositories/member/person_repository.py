"""
Member person repository.
"""
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.org.results import MemberPersonDetailResult
from portal.application.rbac.commands import PagesQueryCommand
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import AuthUser, AuthUserProfile, MemberPerson


class PersonRepository:
    """SQLAlchemy-backed member person repository."""

    def __init__(self, session: Session):
        self._session = session

    @staticmethod
    def _display_name_expr():
        return sa.func.coalesce(AuthUserProfile.preferred_name, AuthUser.email)

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
    ) -> tuple[list[MemberPersonDetailResult], int]:
        items, count = await (
            self._session.select(
                MemberPerson.id,
                MemberPerson.legal_name,
                MemberPerson.user_id,
                AuthUser.email,
                self._display_name_expr().label("display_name"),
            )
            .select_from(MemberPerson)
            .outerjoin(AuthUser, AuthUser.id == MemberPerson.user_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(
                model.keyword,
                lambda: sa.or_(
                    MemberPerson.legal_name.ilike(f"%{model.keyword}%"),
                    AuthUser.email.ilike(f"%{model.keyword}%"),
                ),
            )
            .order_by_with(
                tables=[MemberPerson],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MemberPersonDetailResult)
        )
        return items or [], count

    async def get_by_id(self, person_id: UUID) -> Optional[MemberPersonDetailResult]:
        return await (
            self._session.select(
                MemberPerson.id,
                MemberPerson.legal_name,
                MemberPerson.user_id,
                AuthUser.email,
                self._display_name_expr().label("display_name"),
            )
            .select_from(MemberPerson)
            .outerjoin(AuthUser, AuthUser.id == MemberPerson.user_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(MemberPerson.id == person_id)
            .fetchrow(as_model=MemberPersonDetailResult)
        )

    async def insert_person(self, payload: dict[str, Any]) -> None:
        await self._session.insert(MemberPerson).values(payload).execute()

    async def update_person(self, person_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(MemberPerson)
            .values(**values)
            .where(MemberPerson.id == person_id)
            .execute()
        )
        return affected_rows(result)

    async def link_user(self, person_id: UUID, user_id: UUID) -> int:
        result = await (
            self._session.update(MemberPerson)
            .values(user_id=user_id)
            .where(MemberPerson.id == person_id)
            .execute()
        )
        return affected_rows(result)

    async def user_already_linked(self, user_id: UUID, exclude_person_id: Optional[UUID] = None) -> bool:
        query = (
            self._session.select(MemberPerson.id)
            .where(MemberPerson.user_id == user_id)
        )
        if exclude_person_id:
            query = query.where(MemberPerson.id != exclude_person_id)
        existing_id = await query.fetchval()
        return existing_id is not None
