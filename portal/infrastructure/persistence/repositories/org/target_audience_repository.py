"""
Org target audience catalog repository.
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.org.results import TargetAudienceResult
from portal.infrastructure.persistence.repositories.shared.translation_queries import (
    default_locale_subquery,
    locale_scoped_max,
)
from portal.libs.database import Session
from portal.models import OrgMinistryTargetAudience, OrgTargetAudience, OrgTargetAudienceTranslation


class TargetAudienceRepository:
    """SQLAlchemy-backed org target audience catalog repository."""

    def __init__(self, session: Session):
        self._session = session

    async def list_active(self, locale_id: Optional[UUID]) -> list[TargetAudienceResult]:
        name_expr = locale_scoped_max(OrgTargetAudienceTranslation.name, OrgTargetAudienceTranslation, locale_id)
        if locale_id is None:
            name_expr = sa.func.coalesce(
                name_expr,
                sa.func.max(
                    sa.case(
                        (
                            OrgTargetAudienceTranslation.locale_id == default_locale_subquery(),
                            OrgTargetAudienceTranslation.name,
                        ),
                        else_=None,
                    )
                ),
            )
        rows: list[TargetAudienceResult] = await (
            self._session.select(
                OrgTargetAudience.id,
                OrgTargetAudience.code,
                name_expr.label("name"),
            )
            .select_from(OrgTargetAudience)
            .outerjoin(
                OrgTargetAudienceTranslation,
                OrgTargetAudienceTranslation.target_audience_id == OrgTargetAudience.id,
            )
            .where(OrgTargetAudience.is_active == True)
            .group_by(OrgTargetAudience.id, OrgTargetAudience.code, OrgTargetAudience.sequence)
            .order_by(OrgTargetAudience.sequence, OrgTargetAudience.code)
            .fetch(as_model=TargetAudienceResult)
        )
        return rows or []

    async def fetch_active_by_ids(self, audience_ids: list[UUID]) -> list[TargetAudienceResult]:
        if not audience_ids:
            return []
        rows: list[TargetAudienceResult] = await (
            self._session.select(
                OrgTargetAudience.id,
                OrgTargetAudience.code,
            )
            .select_from(OrgTargetAudience)
            .where(OrgTargetAudience.id.in_(audience_ids))
            .where(OrgTargetAudience.is_active == True)
            .fetch(as_model=TargetAudienceResult)
        )
        return rows or []

    async def list_for_ministry(
        self,
        ministry_id: UUID,
        locale_id: Optional[UUID],
    ) -> list[TargetAudienceResult]:
        name_expr = locale_scoped_max(OrgTargetAudienceTranslation.name, OrgTargetAudienceTranslation, locale_id)
        if locale_id is None:
            name_expr = sa.func.coalesce(
                name_expr,
                sa.func.max(
                    sa.case(
                        (
                            OrgTargetAudienceTranslation.locale_id == default_locale_subquery(),
                            OrgTargetAudienceTranslation.name,
                        ),
                        else_=None,
                    )
                ),
            )
        rows: list[TargetAudienceResult] = await (
            self._session.select(
                OrgTargetAudience.id,
                OrgTargetAudience.code,
                name_expr.label("name"),
            )
            .select_from(OrgMinistryTargetAudience)
            .join(OrgTargetAudience, OrgTargetAudience.id == OrgMinistryTargetAudience.target_audience_id)
            .outerjoin(
                OrgTargetAudienceTranslation,
                OrgTargetAudienceTranslation.target_audience_id == OrgTargetAudience.id,
            )
            .where(OrgMinistryTargetAudience.ministry_id == ministry_id)
            .group_by(OrgTargetAudience.id, OrgTargetAudience.code, OrgTargetAudience.sequence)
            .order_by(OrgTargetAudience.sequence, OrgTargetAudience.code)
            .fetch(as_model=TargetAudienceResult)
        )
        return rows or []
