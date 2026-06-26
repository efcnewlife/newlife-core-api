"""
Locale repository implementation.
"""
from portal.domain.locale.entities import Locale
from portal.libs.database import Session
from portal.models import SystemLocale


class LocaleRepository:
    """SQLAlchemy-backed locale repository."""

    def __init__(self, session: Session):
        self._session = session

    async def list_all(self) -> list[Locale]:
        """
        List non-deleted locales ordered by sequence.
        :return:
        """
        locales: list[Locale] = await (
            self._session.select(
                SystemLocale.id,
                SystemLocale.language_code,
                SystemLocale.script_code,
                SystemLocale.region_code,
                SystemLocale.name,
                SystemLocale.native_name,
                SystemLocale.is_active,
                SystemLocale.is_default,
            )
            .where(SystemLocale.is_deleted == False)
            .order_by(SystemLocale.sequence)
            .fetch(as_model=Locale)
        )
        return locales or []
