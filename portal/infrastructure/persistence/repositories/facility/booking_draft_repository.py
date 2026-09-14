"""
Facility booking draft repository.
"""

from typing import Optional
from uuid import UUID

from portal.application.facility.results import BookingDraftDetailResult, BookingDraftStoredLineResult
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

    async def update_header(self, booking_draft_id: UUID, values: dict) -> None:
        await self._session.update(FacilityBookingDraft).values(**values).where(FacilityBookingDraft.id == booking_draft_id).execute()

    async def replace_lines(self, booking_draft_id: UUID, line_rows: list[dict]) -> None:
        await self._session.delete(FacilityBookingDraftLine).where(FacilityBookingDraftLine.booking_draft_id == booking_draft_id).execute()
        if line_rows:
            await self._session.insert(FacilityBookingDraftLine).values(apply_audit_fields_to_rows(line_rows)).execute()

    async def delete_draft(self, booking_draft_id: UUID) -> None:
        await self._session.delete(FacilityBookingDraftLine).where(FacilityBookingDraftLine.booking_draft_id == booking_draft_id).execute()
        await self._session.delete(FacilityBookingDraft).where(FacilityBookingDraft.id == booking_draft_id).execute()

    async def get_detail(self, booking_draft_id: UUID) -> Optional[BookingDraftDetailResult]:
        row = await (
            self._session.select(FacilityBookingDraft.id, FacilityBookingDraft.user_id, FacilityBookingDraft.date, FacilityBookingDraft.ministry_id)
            .where(FacilityBookingDraft.id == booking_draft_id)
            .fetchrow(as_model=BookingDraftDetailResult)
        )
        if not row:
            return None
        lines = await (
            self._session.select(
                FacilityBookingDraftLine.facility_id, FacilityBookingDraftLine.start_at, FacilityBookingDraftLine.end_at, FacilityBookingDraftLine.sequence
            )
            .where(FacilityBookingDraftLine.booking_draft_id == booking_draft_id)
            .order_by(FacilityBookingDraftLine.sequence.asc())
            .fetch(as_model=BookingDraftStoredLineResult)
        )
        return row.model_copy(update={"lines": lines or []})
