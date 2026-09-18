"""
Facility Recurring Series Draft repository.
"""

from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.facility.results import RecurringSeriesDraftDetailResult, RecurringSeriesDraftStoredRoomResult
from portal.libs.database import Session
from portal.models import FacilityBookingSeriesDraft, FacilityBookingSeriesDraftRoom
from portal.models.mixins.context import apply_audit_fields_to_rows


class RecurringSeriesDraftRepository:
    """SQLAlchemy-backed Recurring Series Draft repository."""

    def __init__(self, session: Session):
        self._session = session

    async def insert_draft(self, payload: dict) -> None:
        await self._session.insert(FacilityBookingSeriesDraft).values(apply_audit_fields_to_rows([payload])).execute()

    async def insert_rooms(self, room_rows: list[dict]) -> None:
        if not room_rows:
            return
        await self._session.insert(FacilityBookingSeriesDraftRoom).values(apply_audit_fields_to_rows(room_rows)).execute()

    async def update_header(self, series_draft_id: UUID, values: dict) -> None:
        await self._session.update(FacilityBookingSeriesDraft).values(**values).where(FacilityBookingSeriesDraft.id == series_draft_id).execute()

    async def replace_rooms(self, series_draft_id: UUID, room_rows: list[dict]) -> None:
        await self._session.delete(FacilityBookingSeriesDraftRoom).where(FacilityBookingSeriesDraftRoom.series_draft_id == series_draft_id).execute()
        if room_rows:
            await self._session.insert(FacilityBookingSeriesDraftRoom).values(apply_audit_fields_to_rows(room_rows)).execute()

    async def delete_draft(self, series_draft_id: UUID) -> None:
        await self._session.delete(FacilityBookingSeriesDraftRoom).where(FacilityBookingSeriesDraftRoom.series_draft_id == series_draft_id).execute()
        await self._session.delete(FacilityBookingSeriesDraft).where(FacilityBookingSeriesDraft.id == series_draft_id).execute()

    async def delete_all_for_user(self, user_id: UUID) -> None:
        owned_draft_ids = sa.select(FacilityBookingSeriesDraft.id).where(FacilityBookingSeriesDraft.user_id == user_id)
        await self._session.delete(FacilityBookingSeriesDraftRoom).where(FacilityBookingSeriesDraftRoom.series_draft_id.in_(owned_draft_ids)).execute()
        await self._session.delete(FacilityBookingSeriesDraft).where(FacilityBookingSeriesDraft.user_id == user_id).execute()

    async def get_detail(self, series_draft_id: UUID) -> Optional[RecurringSeriesDraftDetailResult]:
        row = await (
            self._session.select(
                FacilityBookingSeriesDraft.id,
                FacilityBookingSeriesDraft.user_id,
                FacilityBookingSeriesDraft.title,
                FacilityBookingSeriesDraft.ministry_id,
                FacilityBookingSeriesDraft.first_occurrence_date,
                FacilityBookingSeriesDraft.last_occurrence_date,
                FacilityBookingSeriesDraft.local_start_time,
                FacilityBookingSeriesDraft.local_end_time,
                FacilityBookingSeriesDraft.is_mission_aligned,
                FacilityBookingSeriesDraft.remark,
                FacilityBookingSeriesDraft.surcharge_codes,
                FacilityBookingSeriesDraft.excluded_dates,
            )
            .where(FacilityBookingSeriesDraft.id == series_draft_id)
            .fetchrow(as_model=RecurringSeriesDraftDetailResult)
        )
        if not row:
            return None
        rooms = await (
            self._session.select(FacilityBookingSeriesDraftRoom.facility_id, FacilityBookingSeriesDraftRoom.sequence)
            .where(FacilityBookingSeriesDraftRoom.series_draft_id == series_draft_id)
            .order_by(FacilityBookingSeriesDraftRoom.sequence.asc())
            .fetch(as_model=RecurringSeriesDraftStoredRoomResult)
        )
        return row.model_copy(
            update={"rooms": rooms or [], "surcharge_codes": list(row.surcharge_codes or []), "excluded_dates": list(row.excluded_dates or [])}
        )
