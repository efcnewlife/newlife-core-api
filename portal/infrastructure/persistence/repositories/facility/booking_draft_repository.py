"""
Facility booking draft repository.
"""

from typing import Optional
from uuid import UUID

from portal.libs.database import Session
from portal.models import FacilityBookingDraft, FacilityBookingDraftLine
from portal.models.mixins.context import apply_audit_fields_to_rows


class BookingDraftRepository:
    """SQLAlchemy-backed Booking Draft repository."""

    def __init__(self, session: Session):
        self._session = session

    async def insert_draft(self, payload: dict) -> None:
        await self._session.insert(FacilityBookingDraft).values(apply_audit_fields_to_rows([payload])).execute()

    async def insert_lines(self, line_rows: list[dict]) -> None:
        if not line_rows:
            return
        await self._session.insert(FacilityBookingDraftLine).values(apply_audit_fields_to_rows(line_rows)).execute()

    async def get_detail(self, booking_draft_id: UUID) -> Optional[dict]:
        row = await (
            self._session.select(FacilityBookingDraft.id, FacilityBookingDraft.user_id, FacilityBookingDraft.date, FacilityBookingDraft.ministry_id)
            .where(FacilityBookingDraft.id == booking_draft_id)
            .fetchrow()
        )
        if not row:
            return None
        lines = await (
            self._session.select(
                FacilityBookingDraftLine.facility_id, FacilityBookingDraftLine.start_at, FacilityBookingDraftLine.end_at, FacilityBookingDraftLine.sequence
            )
            .where(FacilityBookingDraftLine.booking_draft_id == booking_draft_id)
            .order_by(FacilityBookingDraftLine.sequence.asc())
            .fetch()
        )
        return dict(row) | {"lines": [dict(line) for line in lines or []]}

    async def delete_draft(self, booking_draft_id: UUID) -> None:
        await self._session.delete(FacilityBookingDraft).where(FacilityBookingDraft.id == booking_draft_id).execute()
