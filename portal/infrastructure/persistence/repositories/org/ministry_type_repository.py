"""
Org ministry type catalog repository.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.org.results import MinistryTypeResult
from portal.infrastructure.persistence.repositories.shared.translation_queries import (
    default_locale_subquery,
    locale_scoped_max,
)
from portal.libs.database import Session
from portal.models import OrgMinistryType, OrgMinistryTypeTranslation


class MinistryTypeRepository:
    """SQLAlchemy-backed org ministry type catalog repository."""

    def __init__(self, session: Session):
        self._session = session

    async def list_active(self, locale_id: Optional[UUID]) -> list[MinistryTypeResult]:
        name_expr = locale_scoped_max(OrgMinistryTypeTranslation.name, OrgMinistryTypeTranslation, locale_id)
        if locale_id is None:
            name_expr = sa.func.coalesce(
                name_expr,
                sa.func.max(
                    sa.case(
                        (
                            OrgMinistryTypeTranslation.locale_id == default_locale_subquery(),
                            OrgMinistryTypeTranslation.name,
                        ),
                        else_=None,
                    )
                ),
            )
        rows: list[MinistryTypeResult] = await (
            self._session.select(
                OrgMinistryType.id,
                OrgMinistryType.code,
                name_expr.label("name"),
            )
            .select_from(OrgMinistryType)
            .outerjoin(
                OrgMinistryTypeTranslation,
                OrgMinistryTypeTranslation.ministry_type_id == OrgMinistryType.id,
            )
            .where(OrgMinistryType.is_active == True)
            .group_by(OrgMinistryType.id, OrgMinistryType.code, OrgMinistryType.sequence)
            .order_by(OrgMinistryType.sequence, OrgMinistryType.code)
            .fetch(as_model=MinistryTypeResult)
        )
        return rows or []

    async def get_active_by_id(self, ministry_type_id: UUID) -> Optional[MinistryTypeResult]:
        row: Optional[MinistryTypeResult] = await (
            self._session.select(
                OrgMinistryType.id,
                OrgMinistryType.code,
            )
            .select_from(OrgMinistryType)
            .where(OrgMinistryType.id == ministry_type_id)
            .where(OrgMinistryType.is_active == True)
            .fetchrow(as_model=MinistryTypeResult)
        )
        return row

    async def get_id_by_code(self, code: str) -> Optional[UUID]:
        ministry_type_id = await (
            self._session.select(OrgMinistryType.id)
            .where(OrgMinistryType.code == code)
            .where(OrgMinistryType.is_active == True)
            .fetchval()
        )
        return ministry_type_id
