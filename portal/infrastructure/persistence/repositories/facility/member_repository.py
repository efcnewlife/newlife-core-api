"""
Facility member (SSO user) read repository.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.facility.commands import MemberPagesQueryCommand
from portal.application.facility.results import MemberDetailResult, MemberListItemResult, MemberMinistryTagResult
from portal.infrastructure.persistence.repositories.shared.translation_queries import ministry_name_fallback
from portal.libs.database import Session
from portal.models import (
    AuthUser,
    AuthUserProfile,
    AuthUserThirdParty,
    OrgMinistry,
    OrgMinistryMember,
    OrgMinistryTranslation,
    SystemLocale,
)


class MemberRepository:
    """Read-only facility member queries."""

    _SQL_EMPTY_STR = sa.literal_column("''")
    _SQL_SPACE_STR = sa.literal_column("' '")

    def __init__(self, session: Session):
        self._session = session

    @classmethod
    def _display_name_expr(cls):
        return sa.func.coalesce(
            AuthUserProfile.preferred_name,
            sa.func.nullif(
                sa.func.trim(
                    sa.func.concat(
                        sa.func.coalesce(AuthUserProfile.first_name, cls._SQL_EMPTY_STR),
                        cls._SQL_SPACE_STR,
                        sa.func.coalesce(AuthUserProfile.last_name, cls._SQL_EMPTY_STR),
                    )
                ),
                cls._SQL_EMPTY_STR,
            ),
            AuthUser.email,
        )

    def _member_base_filter(self):
        return (
            sa.and_(
                AuthUser.is_admin == False,
                AuthUser.is_deleted == False,
                sa.or_(
                    AuthUser.last_login_at.isnot(None),
                    sa.exists(
                        sa.select(AuthUserThirdParty.id).where(
                            AuthUserThirdParty.user_id == AuthUser.id
                        )
                    ),
                ),
            )
        )

    async def fetch_pages(
        self,
        model: MemberPagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[MemberListItemResult], int]:
        items, count = await (
            self._session.select(
                AuthUser.id,
                AuthUser.email,
                self._display_name_expr().label("display_name"),
                AuthUser.last_login_at,
            )
            .select_from(AuthUser)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(self._member_base_filter())
            .where(
                model.ministry_id,
                lambda: sa.exists(
                    sa.select(1).where(
                        OrgMinistryMember.user_id == AuthUser.id,
                        OrgMinistryMember.ministry_id == model.ministry_id,
                    )
                ),
            )
            .where(
                model.keyword,
                lambda: sa.or_(
                    AuthUser.email.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.first_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.last_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.preferred_name.ilike(f"%{model.keyword}%"),
                ),
            )
            .order_by_with(
                tables=[AuthUser],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=MemberListItemResult)
        )
        normalized = [
            MemberListItemResult.model_validate({**item.model_dump(), "ministries": []})
            for item in (items or [])
        ]
        return normalized, count

    async def get_detail(self, user_id: UUID, locale_id: Optional[UUID]) -> Optional[MemberDetailResult]:
        row = await (
            self._session.select(
                AuthUser.id,
                AuthUser.email,
                self._display_name_expr().label("display_name"),
                AuthUser.last_login_at,
            )
            .select_from(AuthUser)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(AuthUser.id == user_id)
            .where(self._member_base_filter())
            .fetchrow(as_model=MemberDetailResult)
        )
        if not row:
            return None
        ministries = await self._fetch_user_ministries(user_id, locale_id)
        data = row.model_dump()
        data["ministries"] = ministries
        return MemberDetailResult.model_validate(data)

    async def _fetch_user_ministries(
        self,
        user_id: UUID,
        locale_id: Optional[UUID],
    ) -> list[MemberMinistryTagResult]:
        translation_join = OrgMinistryTranslation.ministry_id == OrgMinistry.id
        locale_join = OrgMinistryTranslation.locale_id == SystemLocale.id
        query = (
            self._session.select(
                OrgMinistry.id,
                sa.literal_column("''").label("code"),
                ministry_name_fallback(locale_id).label("name"),
            )
            .select_from(OrgMinistryMember)
            .join(OrgMinistry, OrgMinistry.id == OrgMinistryMember.ministry_id)
            .outerjoin(OrgMinistryTranslation, translation_join)
            .outerjoin(SystemLocale, locale_join)
        )
        rows: list[MemberMinistryTagResult] = await (
            query.where(OrgMinistryMember.user_id == user_id)
            .group_by(OrgMinistry.id)
            .fetch(as_model=MemberMinistryTagResult)
        )
        return rows or []
