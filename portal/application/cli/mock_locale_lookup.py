"""
Shared default-locale lookup for Mock QA data lifecycle CLI commands (ADR 0025).
"""

from typing import Optional
from uuid import UUID

from portal.libs.database import Session
from portal.models import SystemLocale


async def resolve_default_locale_id(session: Session, default_locale_code: str) -> Optional[UUID]:
    """Return the active SystemLocale id matching `default_locale_code`, or None."""
    target = default_locale_code.strip().lower()
    rows = (
        await session.select(SystemLocale.id, SystemLocale.language_code).where(SystemLocale.is_active == True).where(SystemLocale.is_deleted == False).fetch()
    )
    for row in rows or []:
        if str(row["language_code"]).strip().lower() == target:
            return row["id"]
    return None
