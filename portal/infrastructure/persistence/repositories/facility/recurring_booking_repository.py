"""
Recurring Booking Series repository.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from portal.application.facility.results import RecurringBookingSeriesResult
from portal.domain.facility.constants import PENDING_PAYMENT_SWEEP_LOCK_CLASS, PENDING_PAYMENT_SWEEP_LOCK_ID, BookingStatus
from portal.libs.database import Session
from portal.models import FacilityBookingSeries


class RecurringBookingRepository:
    """SQLAlchemy-backed Recurring Booking Series repository."""

    def __init__(self, session: Session):
        self._session = session

    async def insert_series(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityBookingSeries).values(payload).execute()

    async def get_by_id(self, series_id: UUID) -> Optional[RecurringBookingSeriesResult]:
        row = await (
            self._session.select(
                FacilityBookingSeries.id,
                FacilityBookingSeries.user_id,
                FacilityBookingSeries.ministry_id,
                FacilityBookingSeries.first_occurrence_date,
                FacilityBookingSeries.last_occurrence_date,
                FacilityBookingSeries.local_start_time,
                FacilityBookingSeries.local_end_time,
                FacilityBookingSeries.status,
                FacilityBookingSeries.payment_hold_expires_at,
                FacilityBookingSeries.quoted_amount,
                FacilityBookingSeries.currency,
                FacilityBookingSeries.is_priority,
                FacilityBookingSeries.updated_by_id,
            )
            .where(FacilityBookingSeries.id == series_id)
            .where(FacilityBookingSeries.is_deleted == False)
            .fetchrow()
        )
        if row is None:
            return None
        return self._to_series_result(row)

    async def update_series(self, series_id: UUID, values: dict[str, Any]) -> None:
        await (
            self._session.update(FacilityBookingSeries)
            .values(**values)
            .where(FacilityBookingSeries.id == series_id)
            .where(FacilityBookingSeries.is_deleted == False)
            .execute()
        )

    async def list_expired_pending_series(self, now: datetime) -> list[RecurringBookingSeriesResult]:
        rows = await (
            self._session.select(
                FacilityBookingSeries.id,
                FacilityBookingSeries.user_id,
                FacilityBookingSeries.ministry_id,
                FacilityBookingSeries.first_occurrence_date,
                FacilityBookingSeries.last_occurrence_date,
                FacilityBookingSeries.local_start_time,
                FacilityBookingSeries.local_end_time,
                FacilityBookingSeries.status,
                FacilityBookingSeries.payment_hold_expires_at,
                FacilityBookingSeries.quoted_amount,
                FacilityBookingSeries.currency,
                FacilityBookingSeries.is_priority,
                FacilityBookingSeries.updated_by_id,
            )
            .where(FacilityBookingSeries.is_deleted == False)
            .where(FacilityBookingSeries.status == BookingStatus.PENDING_PAYMENT.value)
            .where(FacilityBookingSeries.payment_hold_expires_at.isnot(None))
            .where(FacilityBookingSeries.payment_hold_expires_at <= now)
            .order_by(FacilityBookingSeries.payment_hold_expires_at.asc())
            .fetch()
        )
        return [self._to_series_result(row) for row in rows or []]

    async def try_acquire_sweep_lock(self) -> bool:
        locked = await self._session.fetchval("SELECT pg_try_advisory_lock($1, $2)", PENDING_PAYMENT_SWEEP_LOCK_CLASS, PENDING_PAYMENT_SWEEP_LOCK_ID)
        return bool(locked)

    async def release_sweep_lock(self) -> None:
        await self._session.fetchval("SELECT pg_advisory_unlock($1, $2)", PENDING_PAYMENT_SWEEP_LOCK_CLASS, PENDING_PAYMENT_SWEEP_LOCK_ID)

    @staticmethod
    def _to_series_result(row: Any) -> RecurringBookingSeriesResult:
        data = dict(row)
        confirmed_by_id = data.get("updated_by_id")
        if data.get("status") != BookingStatus.CONFIRMED.value:
            confirmed_by_id = None
        quoted_amount = data.get("quoted_amount")
        return RecurringBookingSeriesResult(
            id=data["id"],
            user_id=data["user_id"],
            ministry_id=data.get("ministry_id"),
            first_occurrence_date=data["first_occurrence_date"],
            last_occurrence_date=data["last_occurrence_date"],
            local_start_time=data["local_start_time"],
            local_end_time=data["local_end_time"],
            status=data["status"],
            payment_hold_expires_at=data.get("payment_hold_expires_at"),
            quoted_amount=quoted_amount if quoted_amount is not None else Decimal("0"),
            currency=data.get("currency") or "CAD",
            is_priority=bool(data.get("is_priority")),
            occurrence_count=0,
            confirmed_by_id=confirmed_by_id,
        )
