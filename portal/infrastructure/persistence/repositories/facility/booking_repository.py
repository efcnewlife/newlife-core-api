"""
Facility booking repository.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.facility.commands import BookingPagesQueryCommand, UpdateBookingCommand
from portal.application.facility.results import (
    BookingDetailResult,
    BookingListItemResult,
    BookingRoomLineResult,
    BookingSlotResult,
)
from portal.domain.facility.constants import BookingSlotStatus, BookingStatus
from portal.libs.database import Session
from portal.libs.database.execute_result import affected_rows
from portal.models import (
    AuthUser,
    AuthUserProfile,
    AuthUserThirdParty,
    FacilityBooking,
    FacilityBookingRoom,
    FacilityBookingSlot,
    FacilityRoom,
    FacilityRoomTranslation,
)


class BookingRepository:
    """SQLAlchemy-backed facility booking repository."""

    _SQL_EMPTY_STR = sa.literal_column("''")
    _SQL_SPACE_STR = sa.literal_column("' '")

    def __init__(self, session: Session):
        self._session = session

    @classmethod
    def _display_name_expr(cls):
        return sa.func.coalesce(
            AuthUserProfile.preferred_name,
            sa.func.nullif(
                sa.func.trim(
                    sa.func.concat(
                        sa.func.coalesce(AuthUserProfile.first_name, cls._SQL_EMPTY_STR),
                        cls._SQL_SPACE_STR,
                        sa.func.coalesce(AuthUserProfile.last_name, cls._SQL_EMPTY_STR),
                    )
                ),
                cls._SQL_EMPTY_STR,
            ),
            AuthUser.email,
        )

    def _list_query(self, locale_id: Optional[UUID]):
        room_name = FacilityRoom.code
        if locale_id:
            room_name = sa.func.coalesce(FacilityRoomTranslation.name, FacilityRoom.code)

        query = (
            self._session.select(
                FacilityBooking.id,
                FacilityBooking.user_id,
                AuthUser.email.label("user_email"),
                self._display_name_expr().label("user_display_name"),
                FacilityBooking.facility_id,
                room_name.label("facility_name"),
                FacilityBooking.booking_type,
                FacilityBooking.start_at,
                FacilityBooking.end_at,
                FacilityBooking.status,
                FacilityBooking.quoted_amount,
                FacilityBooking.currency,
                FacilityBooking.created_at,
            )
            .select_from(FacilityBooking)
            .join(AuthUser, AuthUser.id == FacilityBooking.user_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .outerjoin(FacilityRoom, FacilityRoom.id == FacilityBooking.facility_id)
        )
        if locale_id:
            query = query.outerjoin(
                FacilityRoomTranslation,
                sa.and_(
                    FacilityRoomTranslation.room_id == FacilityRoom.id,
                    FacilityRoomTranslation.locale_id == locale_id,
                ),
            )
        return query

    async def fetch_pages(
        self,
        model: BookingPagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[BookingListItemResult], int]:
        items, count = await (
            self._list_query(locale_id)
            .where(FacilityBooking.is_deleted == model.deleted)
            .where(model.facility_id, lambda: FacilityBooking.facility_id == model.facility_id)
            .where(model.user_id, lambda: FacilityBooking.user_id == model.user_id)
            .where(model.status, lambda: FacilityBooking.status == model.status)
            .where(model.booking_type, lambda: FacilityBooking.booking_type == model.booking_type)
            .where(model.date_from is not None, lambda: FacilityBooking.start_at >= model.date_from)
            .where(model.date_to is not None, lambda: FacilityBooking.start_at <= model.date_to)
            .where(
                model.keyword,
                lambda: sa.or_(
                    AuthUser.email.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.first_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.last_name.ilike(f"%{model.keyword}%"),
                    AuthUserProfile.preferred_name.ilike(f"%{model.keyword}%"),
                ),
            )
            .order_by_with(
                tables=[FacilityBooking],
                order_by=model.order_by,
                descending=model.descending,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=BookingListItemResult)
        )
        return items or [], count

    async def get_detail(self, booking_id: UUID, locale_id: Optional[UUID]) -> Optional[BookingDetailResult]:
        row = await (
            self._session.select(
                FacilityBooking.id,
                FacilityBooking.user_id,
                AuthUser.email.label("user_email"),
                self._display_name_expr().label("user_display_name"),
                FacilityBooking.facility_id,
                FacilityBooking.ministry_id,
                FacilityBooking.booking_type,
                FacilityBooking.start_at,
                FacilityBooking.end_at,
                FacilityBooking.recurrence_rule,
                FacilityBooking.recurrence_end_at,
                FacilityBooking.status,
                FacilityBooking.is_mission_aligned,
                FacilityBooking.subtotal_amount,
                FacilityBooking.discount_percent,
                FacilityBooking.discount_amount,
                FacilityBooking.surcharge_amount,
                FacilityBooking.quoted_amount,
                FacilityBooking.deposit_amount,
                FacilityBooking.currency,
                FacilityBooking.cancelled_at,
                FacilityBooking.cancel_reason,
                FacilityBooking.remark,
            )
            .select_from(FacilityBooking)
            .join(AuthUser, AuthUser.id == FacilityBooking.user_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .where(FacilityBooking.id == booking_id)
            .where(FacilityBooking.is_deleted == False)
            .fetchrow(as_model=BookingDetailResult)
        )
        if not row:
            return None
        rooms = await self._fetch_booking_rooms(booking_id, locale_id)
        slots = await self._fetch_booking_slots(booking_id)
        data = row.model_dump()
        data["rooms"] = rooms
        data["slots"] = slots
        return BookingDetailResult.model_validate(data)

    async def _fetch_booking_rooms(
        self,
        booking_id: UUID,
        locale_id: Optional[UUID],
    ) -> list[BookingRoomLineResult]:
        room_name = FacilityRoom.code
        if locale_id:
            room_name = sa.func.coalesce(
                sa.select(FacilityRoomTranslation.name)
                .where(
                    FacilityRoomTranslation.room_id == FacilityRoom.id,
                    FacilityRoomTranslation.locale_id == locale_id,
                )
                .limit(1)
                .scalar_subquery(),
                FacilityRoom.code,
            )

        rows: list[BookingRoomLineResult] = await (
            self._session.select(
                FacilityBookingRoom.id,
                FacilityBookingRoom.facility_id,
                room_name.label("facility_name"),
                FacilityRoom.code.label("facility_code"),
                FacilityBookingRoom.sequence,
                FacilityBookingRoom.start_at,
                FacilityBookingRoom.end_at,
                FacilityBookingRoom.billed_hours,
                FacilityBookingRoom.pricing_tier_used,
                FacilityBookingRoom.rental_rate_id,
                FacilityBookingRoom.line_subtotal,
            )
            .select_from(FacilityBookingRoom)
            .join(FacilityRoom, FacilityRoom.id == FacilityBookingRoom.facility_id)
            .where(FacilityBookingRoom.facility_booking_id == booking_id)
            .order_by(FacilityBookingRoom.sequence.asc())
            .fetch(as_model=BookingRoomLineResult)
        )
        return rows or []

    async def _fetch_booking_slots(self, booking_id: UUID) -> list[BookingSlotResult]:
        rows: list[BookingSlotResult] = await (
            self._session.select(
                FacilityBookingSlot.id,
                FacilityBookingSlot.facility_id,
                FacilityBookingSlot.start_at,
                FacilityBookingSlot.end_at,
                FacilityBookingSlot.status,
            )
            .where(FacilityBookingSlot.facility_booking_id == booking_id)
            .order_by(FacilityBookingSlot.start_at.asc())
            .fetch(as_model=BookingSlotResult)
        )
        return rows or []

    async def exists_by_id(self, booking_id: UUID) -> bool:
        row = await (
            self._session.select(FacilityBooking.id)
            .where(FacilityBooking.id == booking_id)
            .where(FacilityBooking.is_deleted == False)
            .fetchrow()
        )
        return row is not None

    async def has_confirmed_slot_overlap(
        self,
        facility_id: UUID,
        start_at: datetime,
        end_at: datetime,
        exclude_booking_id: Optional[UUID] = None,
    ) -> bool:
        query = (
            self._session.select(sa.func.count())
            .select_from(FacilityBookingSlot)
            .where(FacilityBookingSlot.facility_id == facility_id)
            .where(FacilityBookingSlot.status == BookingSlotStatus.CONFIRMED.value)
            .where(FacilityBookingSlot.start_at < end_at)
            .where(FacilityBookingSlot.end_at > start_at)
        )
        if exclude_booking_id:
            query = query.where(FacilityBookingSlot.facility_booking_id != exclude_booking_id)
        count = await query.fetchval()
        return bool(count and count > 0)

    async def cancel_booking(
        self,
        booking_id: UUID,
        cancelled_by_id: Optional[UUID],
        cancel_reason: Optional[str],
        cancel_slots: bool,
    ) -> None:
        now = datetime.now(timezone.utc)
        await (
            self._session.update(FacilityBooking)
            .values(
                status=BookingStatus.CANCELLED.value,
                cancelled_at=now,
                cancelled_by_id=cancelled_by_id,
                cancel_reason=cancel_reason,
            )
            .where(FacilityBooking.id == booking_id)
            .execute_rowcount()
        )
        if cancel_slots:
            await (
                self._session.update(FacilityBookingSlot)
                .values(status=BookingSlotStatus.CANCELLED.value)
                .where(FacilityBookingSlot.facility_booking_id == booking_id)
                .execute_rowcount()
            )

    async def update_booking_header(
        self,
        booking_id: UUID,
        values: dict,
    ) -> None:
        await (
            self._session.update(FacilityBooking)
            .values(**values)
            .where(FacilityBooking.id == booking_id)
            .execute_rowcount()
        )

    async def replace_booking_rooms(
        self,
        booking_id: UUID,
        room_rows: list[dict],
    ) -> None:
        await (
            self._session.delete(FacilityBookingRoom)
            .where(FacilityBookingRoom.facility_booking_id == booking_id)
            .execute_rowcount()
        )
        if room_rows:
            await self._session.insert(FacilityBookingRoom).values(room_rows).execute_rowcount()

    async def replace_booking_slots(
        self,
        booking_id: UUID,
        slot_rows: list[dict],
    ) -> None:
        await (
            self._session.delete(FacilityBookingSlot)
            .where(FacilityBookingSlot.facility_booking_id == booking_id)
            .execute_rowcount()
        )
        if slot_rows:
            await self._session.insert(FacilityBookingSlot).values(slot_rows).execute_rowcount()

    async def get_booking_type_and_flags(self, booking_id: UUID) -> Optional[dict]:
        return await (
            self._session.select(
                FacilityBooking.booking_type,
                FacilityBooking.is_mission_aligned,
                FacilityBooking.currency,
            )
            .where(FacilityBooking.id == booking_id)
            .fetchrow()
        )
