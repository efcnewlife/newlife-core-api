"""
Facility booking override audit log repository (read-only).
"""
from typing import Optional
from uuid import UUID

import sqlalchemy as sa

from portal.application.facility.commands import OverrideLogPagesQueryCommand
from portal.application.facility.results import OverrideLogResult
from portal.libs.database import Session
from portal.models import AuthUser, AuthUserProfile, FacilityBookingOverrideLog, FacilityRoom


class OverrideLogRepository:
    """Append-only override log reads."""

    def __init__(self, session: Session):
        self._session = session

    async def fetch_pages(
        self,
        model: OverrideLogPagesQueryCommand,
        locale_id: Optional[UUID],
    ) -> tuple[list[OverrideLogResult], int]:
        room_name = FacilityRoom.code
        if locale_id:
            from portal.models import FacilityRoomTranslation

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

        overridden_by_name = sa.func.coalesce(
            AuthUserProfile.preferred_name,
            AuthUser.email,
        )

        items, count = await (
            self._session.select(
                FacilityBookingOverrideLog.id,
                FacilityBookingOverrideLog.facility_booking_id,
                FacilityBookingOverrideLog.overridden_booking_id,
                FacilityBookingOverrideLog.overridden_by_id,
                overridden_by_name.label("overridden_by_name"),
                FacilityBookingOverrideLog.facility_id,
                room_name.label("facility_name"),
                FacilityBookingOverrideLog.outcome,
                FacilityBookingOverrideLog.reason,
                FacilityBookingOverrideLog.created_at,
                FacilityBookingOverrideLog.created_by,
            )
            .select_from(FacilityBookingOverrideLog)
            .join(AuthUser, AuthUser.id == FacilityBookingOverrideLog.overridden_by_id)
            .outerjoin(AuthUserProfile, AuthUserProfile.user_id == AuthUser.id)
            .outerjoin(FacilityRoom, FacilityRoom.id == FacilityBookingOverrideLog.facility_id)
            .where(model.facility_id, lambda: FacilityBookingOverrideLog.facility_id == model.facility_id)
            .where(
                model.overridden_by_id,
                lambda: FacilityBookingOverrideLog.overridden_by_id == model.overridden_by_id,
            )
            .where(model.date_from, lambda: FacilityBookingOverrideLog.created_at >= model.date_from)
            .where(model.date_to, lambda: FacilityBookingOverrideLog.created_at <= model.date_to)
            .order_by_with(
                tables=[FacilityBookingOverrideLog],
                order_by=model.order_by or "created_at",
                descending=model.descending if model.order_by else True,
            )
            .limit(model.page_size)
            .offset(model.page * model.page_size)
            .fetchpages(no_order_by=False, as_model=OverrideLogResult)
        )
        return items or [], count
