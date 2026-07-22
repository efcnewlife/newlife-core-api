"""
Facility room blackout repository.
"""
from datetime import date, datetime, time
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa

from portal.application.facility.results import RoomBlackoutResult
from portal.application.rbac.commands import PagesQueryCommand
from portal.domain.facility.constants import RoomBlackoutKind
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import FacilityRoomBlackout

LOCAL_TZ = ZoneInfo("America/Toronto")


class RoomBlackoutRepository:
    """SQLAlchemy-backed room blackout repository."""

    def __init__(self, session: Session):
        self._session = session

    def _base_select(self):
        return self._session.select(
            FacilityRoomBlackout.id,
            FacilityRoomBlackout.facility_id,
            FacilityRoomBlackout.name,
            FacilityRoomBlackout.reason,
            FacilityRoomBlackout.kind,
            FacilityRoomBlackout.blackout_date,
            FacilityRoomBlackout.days_of_week_mask,
            FacilityRoomBlackout.start_time,
            FacilityRoomBlackout.end_time,
            FacilityRoomBlackout.is_active,
            FacilityRoomBlackout.effective_from,
            FacilityRoomBlackout.effective_to,
            FacilityRoomBlackout.created_at,
            FacilityRoomBlackout.created_by,
            FacilityRoomBlackout.updated_at,
            FacilityRoomBlackout.updated_by,
            FacilityRoomBlackout.delete_reason,
        )

    async def fetch_pages(
        self,
        model: PagesQueryCommand,
        facility_id: Optional[UUID] = None,
    ) -> tuple[list[RoomBlackoutResult], int]:
        query = (
            self._base_select()
            .where(FacilityRoomBlackout.is_deleted == model.deleted)
            .where(
                model.keyword,
                lambda: sa.or_(
                    FacilityRoomBlackout.name.ilike(f"%{model.keyword}%"),
                    FacilityRoomBlackout.reason.ilike(f"%{model.keyword}%"),
                ),
            )
        )
        if facility_id is not None:
            query = query.where(
                sa.or_(
                    FacilityRoomBlackout.facility_id == facility_id,
                    FacilityRoomBlackout.facility_id.is_(None),
                )
            )
        items, count = await (
            query.order_by_with(
                tables=[FacilityRoomBlackout],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=RoomBlackoutResult)
        )
        return items or [], count

    async def list_by_facility(self, facility_id: Optional[UUID]) -> list[RoomBlackoutResult]:
        query = (
            self._base_select()
            .where(FacilityRoomBlackout.is_deleted == False)
        )
        if facility_id is None:
            query = query.where(FacilityRoomBlackout.facility_id.is_(None))
        else:
            query = query.where(
                sa.or_(
                    FacilityRoomBlackout.facility_id == facility_id,
                    FacilityRoomBlackout.facility_id.is_(None),
                )
            )
        items: list[RoomBlackoutResult] = await (
            query.order_by(FacilityRoomBlackout.start_time)
            .fetch(as_model=RoomBlackoutResult)
        )
        return items or []

    async def get_by_id(self, blackout_id: UUID) -> Optional[RoomBlackoutResult]:
        return await (
            self._base_select()
            .where(FacilityRoomBlackout.id == blackout_id)
            .fetchrow(as_model=RoomBlackoutResult)
        )

    async def insert_blackout(self, payload: dict[str, Any]) -> None:
        await self._session.insert(FacilityRoomBlackout).values(payload).execute()

    async def update_blackout(self, blackout_id: UUID, values: dict[str, Any]) -> int:
        result = await (
            self._session.update(FacilityRoomBlackout)
            .values(**values)
            .where(FacilityRoomBlackout.id == blackout_id)
            .where(FacilityRoomBlackout.is_deleted == False)
            .execute()
        )
        return affected_rows(result)

    async def delete_soft(self, blackout_id: UUID, reason: Optional[str]) -> None:
        await (
            self._session.update(FacilityRoomBlackout)
            .values(is_deleted=True, delete_reason=reason)
            .where(FacilityRoomBlackout.id == blackout_id)
            .execute()
        )

    async def delete_hard(self, blackout_id: UUID) -> None:
        await (
            self._session.delete(FacilityRoomBlackout)
            .where(FacilityRoomBlackout.id == blackout_id)
            .execute()
        )

    async def restore_blackout(self, blackout_id: UUID) -> None:
        await (
            self._session.update(FacilityRoomBlackout)
            .values(is_deleted=False, delete_reason=None)
            .where(FacilityRoomBlackout.id == blackout_id)
            .execute()
        )

    @staticmethod
    def effective_dates_overlap(
        left_from: Optional[date],
        left_to: Optional[date],
        right_from: Optional[date],
        right_to: Optional[date],
    ) -> bool:
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

    @staticmethod
    def scopes_overlap(left_facility_id: Optional[UUID], right_facility_id: Optional[UUID]) -> bool:
        """Campus-wide (NULL) overlaps every room; otherwise require same room."""
        if left_facility_id is None or right_facility_id is None:
            return True
        return left_facility_id == right_facility_id

    @staticmethod
    def applies_on_date(item: RoomBlackoutResult, target_date: date) -> bool:
        if item.kind == RoomBlackoutKind.ONE_OFF.value:
            return item.blackout_date == target_date
        if item.effective_from and target_date < item.effective_from:
            return False
        if item.effective_to and target_date > item.effective_to:
            return False
        if item.days_of_week_mask is None:
            return False
        day_bit = 1 << target_date.weekday()
        return (item.days_of_week_mask & day_bit) != 0

    async def list_active_overlapping_candidates(
        self,
        facility_id: Optional[UUID],
        kind: str,
        exclude_blackout_id: Optional[UUID] = None,
    ) -> list[RoomBlackoutResult]:
        query = (
            self._base_select()
            .where(FacilityRoomBlackout.is_deleted == False)
            .where(FacilityRoomBlackout.is_active == True)
            .where(FacilityRoomBlackout.kind == kind)
        )
        if facility_id is None:
            pass
        else:
            query = query.where(
                sa.or_(
                    FacilityRoomBlackout.facility_id == facility_id,
                    FacilityRoomBlackout.facility_id.is_(None),
                )
            )
        if exclude_blackout_id:
            query = query.where(FacilityRoomBlackout.id != exclude_blackout_id)
        items: list[RoomBlackoutResult] = await query.fetch(as_model=RoomBlackoutResult)
        return items or []

    async def list_active_for_room_day(
        self,
        facility_id: UUID,
        target_date: date,
    ) -> list[RoomBlackoutResult]:
        """Active blackouts that apply to a room on a local calendar date."""
        day_bit = 1 << target_date.weekday()
        items: list[RoomBlackoutResult] = await (
            self._base_select()
            .where(FacilityRoomBlackout.is_deleted == False)
            .where(FacilityRoomBlackout.is_active == True)
            .where(
                sa.or_(
                    FacilityRoomBlackout.facility_id == facility_id,
                    FacilityRoomBlackout.facility_id.is_(None),
                )
            )
            .where(
                sa.or_(
                    sa.and_(
                        FacilityRoomBlackout.kind == RoomBlackoutKind.ONE_OFF.value,
                        FacilityRoomBlackout.blackout_date == target_date,
                    ),
                    sa.and_(
                        FacilityRoomBlackout.kind == RoomBlackoutKind.RECURRING.value,
                        (FacilityRoomBlackout.days_of_week_mask.op("&")(day_bit)) != 0,
                        sa.or_(
                            FacilityRoomBlackout.effective_from.is_(None),
                            FacilityRoomBlackout.effective_from <= target_date,
                        ),
                        sa.or_(
                            FacilityRoomBlackout.effective_to.is_(None),
                            FacilityRoomBlackout.effective_to >= target_date,
                        ),
                    ),
                )
            )
            .order_by(FacilityRoomBlackout.start_time)
            .fetch(as_model=RoomBlackoutResult)
        )
        return items or []

    def slot_overlaps_blackouts(
        self,
        blackouts: list[RoomBlackoutResult],
        slot_start_local: time,
        slot_end_local: time,
    ) -> bool:
        for item in blackouts:
            if self.time_ranges_overlap(
                slot_start_local,
                slot_end_local,
                item.start_time,
                item.end_time,
            ):
                return True
        return False

    async def has_blackout_overlap(
        self,
        facility_id: UUID,
        start_at: datetime,
        end_at: datetime,
    ) -> bool:
        """Return True when [start_at, end_at) overlaps an active blackout in Toronto local time."""
        local_start = start_at.astimezone(LOCAL_TZ)
        local_end = end_at.astimezone(LOCAL_TZ)
        if local_start.date() != local_end.date():
            # Cross-midnight bookings are out of scope; treat as overlapping any blackout on either day.
            days = {local_start.date(), local_end.date()}
        else:
            days = {local_start.date()}
        for day in days:
            blackouts = await self.list_active_for_room_day(facility_id, day)
            if not blackouts:
                continue
            if day == local_start.date() and day == local_end.date():
                if self.slot_overlaps_blackouts(blackouts, local_start.time(), local_end.time()):
                    return True
            elif day == local_start.date():
                if self.slot_overlaps_blackouts(blackouts, local_start.time(), time(23, 59, 59)):
                    return True
            else:
                if self.slot_overlaps_blackouts(blackouts, time(0, 0), local_end.time()):
                    return True
        return False
