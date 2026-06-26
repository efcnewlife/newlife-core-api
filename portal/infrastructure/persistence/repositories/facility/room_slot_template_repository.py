"""
Facility room slot template repository.
"""
from datetime import date, time
from typing import Any, Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.facility.results import RoomSlotTemplateResult
from portal.application.rbac.commands import PagesQueryCommand
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import FacilityRoomSlotTemplate


class RoomSlotTemplateRepository:
    """SQLAlchemy-backed room slot template repository."""

    def __init__(self, session: Session):
        self._session = session

    def _base_select(self):
        return self._session.select(
            FacilityRoomSlotTemplate.id,
            FacilityRoomSlotTemplate.facility_id,
            FacilityRoomSlotTemplate.name,
            FacilityRoomSlotTemplate.days_of_week_mask,
            FacilityRoomSlotTemplate.start_time,
            FacilityRoomSlotTemplate.end_time,
            FacilityRoomSlotTemplate.slot_duration_minutes,
            FacilityRoomSlotTemplate.is_active,
            FacilityRoomSlotTemplate.effective_from,
            FacilityRoomSlotTemplate.effective_to,
            FacilityRoomSlotTemplate.created_at,
            FacilityRoomSlotTemplate.created_by,
            FacilityRoomSlotTemplate.updated_at,
            FacilityRoomSlotTemplate.updated_by,
            FacilityRoomSlotTemplate.delete_reason,
        )

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        facility_id: Optional[UUID] = None,
    ) -> tuple[list[RoomSlotTemplateResult], int]:
        query = (
            self._base_select()
            .where(FacilityRoomSlotTemplate.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: FacilityRoomSlotTemplate.name.ilike(f"%{model.keyword}%"),
            )
        )
        if facility_id:
            query = query.where(FacilityRoomSlotTemplate.facility_id == facility_id)
        items, count = await (
            query.order_by_with(
                tables=[FacilityRoomSlotTemplate],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RoomSlotTemplateResult)
        )
        return items or [], count

    async def list_by_facility(self, facility_id: UUID) -> list[RoomSlotTemplateResult]:
        items: list[RoomSlotTemplateResult] = await (
            self._base_select()
            .where(FacilityRoomSlotTemplate.is_deleted == False)
            .where(FacilityRoomSlotTemplate.facility_id == facility_id)
            .order_by(FacilityRoomSlotTemplate.days_of_week_mask, FacilityRoomSlotTemplate.start_time)
            .fetch(as_model=RoomSlotTemplateResult)
        )
        return items or []

    async def get_by_id(self, template_id: UUID) -> Optional[RoomSlotTemplateResult]:
        return await (
            self._base_select()
            .where(FacilityRoomSlotTemplate.id == template_id)
            .fetchrow(as_model=RoomSlotTemplateResult)
        )

    async def insert_template(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRoomSlotTemplate).values(payload).execute()

    async def update_template(self, template_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRoomSlotTemplate)
            .values(**values)
            .where(FacilityRoomSlotTemplate.id == template_id)
            .where(FacilityRoomSlotTemplate.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_soft(self, template_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRoomSlotTemplate)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRoomSlotTemplate.id == template_id)
            .execute()
        )

    async def delete_hard(self, template_id: UUID) -> None:
        await (
            self._session.delete(FacilityRoomSlotTemplate)
            .where(FacilityRoomSlotTemplate.id == template_id)
            .execute()
        )

    async def restore_template(self, template_id: UUID) -> None:
        await (
            self._session.update(FacilityRoomSlotTemplate)
            .values(is_deleted=False, delete_reason=None)
            .where(FacilityRoomSlotTemplate.id == template_id)
            .execute()
        )

    @staticmethod
    def effective_dates_overlap(
        left_from: Optional[date],
        left_to: Optional[date],
        right_from: Optional[date],
        right_to: Optional[date],
    ) -> bool:
        """Return True when two optional effective date ranges overlap."""
        if left_from and right_to and left_from > right_to:
            return False
        if right_from and left_to and right_from > left_to:
            return False
        return True

    @staticmethod
    def time_ranges_overlap(
        left_start: time,
        left_end: time,
        right_start: time,
        right_end: time,
    ) -> bool:
        return left_start < right_end and right_start < left_end

    async def list_active_overlapping_candidates(
        self,
        facility_id: UUID,
        days_of_week_mask: int,
        exclude_template_id: Optional[UUID] = None,
    ) -> list[RoomSlotTemplateResult]:
        """
        Active templates for overlap validation on same room and shared weekday(s).
        """
        query = (
            self._base_select()
            .where(FacilityRoomSlotTemplate.is_deleted == False)
            .where(FacilityRoomSlotTemplate.is_active == True)
            .where(FacilityRoomSlotTemplate.facility_id == facility_id)
            .where(
                (FacilityRoomSlotTemplate.days_of_week_mask.op("&")(days_of_week_mask)) != 0
            )
        )
        if exclude_template_id:
            query = query.where(FacilityRoomSlotTemplate.id != exclude_template_id)
        items: list[RoomSlotTemplateResult] = await query.fetch(as_model=RoomSlotTemplateResult)
        return items or []

    async def list_active_for_day(
        self,
        facility_id: UUID,
        day_of_week: int,
    ) -> list[RoomSlotTemplateResult]:
        """Active templates that apply on a given ISO weekday."""
        day_bit = 1 << day_of_week
        items: list[RoomSlotTemplateResult] = await (
            self._base_select()
            .where(FacilityRoomSlotTemplate.is_deleted == False)
            .where(FacilityRoomSlotTemplate.is_active == True)
            .where(FacilityRoomSlotTemplate.facility_id == facility_id)
            .where((FacilityRoomSlotTemplate.days_of_week_mask.op("&")(day_bit)) != 0)
            .order_by(FacilityRoomSlotTemplate.start_time)
            .fetch(as_model=RoomSlotTemplateResult)
        )
        return items or []
