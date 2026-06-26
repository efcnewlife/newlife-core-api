"""
Verb repository implementation.
"""
from uuid import UUID

import sqlalchemy as sa

from portal.domain.rbac.entities import VerbListItem
from portal.libs.database import Session
from portal.models import AuthVerb, AuthVerbTranslation


class VerbRepository:
    """SQLAlchemy-backed verb repository."""

    def __init__(self, session: Session):
        self._session = session

    async def list_active_by_locale(self, locale_id: UUID) -> list[VerbListItem]:
        """
        List active verbs with translations for the given locale.
        :param locale_id:
        :return:
        """
        verbs: list[VerbListItem] = await (
            self._session.select(
                AuthVerb.id,
                AuthVerb.action,
                AuthVerbTranslation.name,
                AuthVerbTranslation.description,
            )
            .select_from(AuthVerb)
            .join(
                AuthVerbTranslation,
                sa.and_(
                    AuthVerbTranslation.verb_id == AuthVerb.id,
                    AuthVerbTranslation.locale_id == locale_id,
                ),
            )
            .where(AuthVerb.is_active == True)
            .where(AuthVerb.is_deleted == False)
            .order_by(AuthVerb.created_at)
            .fetch(as_model=VerbListItem)
        )
        return verbs or []
