"""
Recurring Booking Series repository.
"""

from typing import Any

from portal.libs.database import Session
from portal.models import FacilityBookingSeries


class RecurringBookingRepository:
    """SQLAlchemy-backed Recurring Booking Series repository."""

    def __init__(self, session: Session):
        self._session = session

    async def insert_series(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityBookingSeries).values(payload).execute()
