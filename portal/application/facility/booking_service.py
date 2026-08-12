"""
Facility booking admin application service.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from portal.application.facility.commands import (
    BookingPagesQueryCommand,
    CancelBookingCommand,
    CreateBookingCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateBookingCommand,
)
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.results import BookingDetailResult, BookingListItemResult, BookingPageResult
from portal.application.org.results import CreateIdResult
from portal.application.system.setting_service import SettingService
from portal.domain.facility.constants import (
    BookingErrorCode,
    BookingSlotStatus,
    BookingStatus,
    BookingType,
    RentalPolicySettingKey,
)
from portal.exceptions.responses import (
    BadRequestException,
    ConflictErrorException,
    ForbiddenException,
    NotFoundException,
)
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import (
    RoomBlackoutRepository,
)
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.domain.org.constants import MinistryStatus
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class BookingService:
    """Admin booking operations (list, detail, cancel, update)."""

    def __init__(
        self,
        booking_repository: BookingRepository,
        pricing_service: PricingService,
        rental_repository: RentalRepository,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
    ):
        self._repository = booking_repository
        self._pricing_service = pricing_service
        self._rental_repository = rental_repository
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _resolved_locale_id(self) -> Optional[UUID]:
        if self._req_ctx and self._req_ctx.resolved_locale_id:
            return self._req_ctx.resolved_locale_id
        return None

    @staticmethod
    def _billed_hours(start_at: datetime, end_at: datetime) -> Decimal:
        delta = end_at - start_at
        hours = Decimal(str(delta.total_seconds())) / Decimal("3600")
        return hours.quantize(Decimal("0.01"))

    @distributed_trace()
    async def get_booking_pages(self, command: BookingPagesQueryCommand) -> BookingPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return BookingPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_booking_by_id(self, booking_id: UUID) -> BookingDetailResult:
        row = await self._repository.get_detail(booking_id, self._resolved_locale_id())
        if not row:
            raise NotFoundException(detail="Booking not found")
        return row

    @distributed_trace()
    async def cancel_booking(self, booking_id: UUID, command: CancelBookingCommand) -> None:
        if not await self._repository.exists_by_id(booking_id):
            raise NotFoundException(detail="Booking not found")
        cancelled_by_id = self._user_ctx.user_id if self._user_ctx else None
        cancel_slots = command.scope != "series"
        await self._repository.cancel_booking(
            booking_id=booking_id,
            cancelled_by_id=cancelled_by_id,
            cancel_reason=command.cancel_reason,
            cancel_slots=cancel_slots,
        )

    @distributed_trace()
    async def update_booking(self, booking_id: UUID, command: UpdateBookingCommand) -> BookingDetailResult:
        if command.end_at <= command.start_at:
            raise BadRequestException(detail="end_at must be after start_at")
        if not command.rooms:
            raise BadRequestException(detail="At least one room is required")

        await self._validate_ministry_booking_gate(command.ministry_id)

        meta = await self._repository.get_booking_type_and_flags(booking_id)
        if not meta:
            raise NotFoundException(detail="Booking not found")

        max_rooms = await self._rental_repository.get_policy_amount(
            RentalPolicySettingKey.MAX_ROOMS_PER_BOOKING,
            None,
        )
        max_rooms_int = int(max_rooms) if max_rooms is not None else 3
        if len(command.rooms) > max_rooms_int:
            raise BadRequestException(detail=f"At most {max_rooms_int} rooms per booking")

        local_tz = await self._setting_service.get_facility_timezone()
        for line in command.rooms:
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            await self._raise_if_room_unavailable(
                facility_id=line.facility_id,
                start_at=start_at,
                end_at=end_at,
                local_tz=local_tz,
                exclude_booking_id=booking_id,
            )

        quote_lines = []
        for line in command.rooms:
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            quote_lines.append(
                PreviewQuoteRoomLineCommand(
                    facility_id=line.facility_id,
                    billed_hours=self._billed_hours(start_at, end_at),
                )
            )

        booking_type_value = meta["booking_type"] if isinstance(meta, dict) else meta.booking_type
        currency_value = meta.get("currency") if isinstance(meta, dict) else meta.currency
        booking_type = BookingType(booking_type_value)
        currency = currency_value or "CAD"
        quote = await self._pricing_service.preview_quote(
            PreviewQuoteCommand(
                booking_type=booking_type,
                is_mission_aligned=command.is_mission_aligned,
                currency=currency,
                room_lines=quote_lines,
                surcharge_codes=command.surcharge_codes,
            )
        )

        primary_facility_id = command.rooms[0].facility_id
        room_rows = []
        slot_rows = []
        for idx, line in enumerate(command.rooms):
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            quoted_line = quote.room_lines[idx]
            room_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    sequence=line.sequence,
                    start_at=start_at,
                    end_at=end_at,
                    billed_hours=quoted_line.billed_hours,
                    rental_rate_name=quoted_line.rental_rate_name,
                    billing_unit=quoted_line.billing_unit,
                    unit_amount=quoted_line.unit_amount,
                    currency=quoted_line.currency,
                    applicability=quoted_line.applicability,
                    is_default=quoted_line.is_default,
                    line_subtotal=quoted_line.line_subtotal,
                )
            )
            slot_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
            )

        total_billed = sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
        await self._repository.update_booking_header(
            booking_id,
            dict(
                facility_id=primary_facility_id,
                ministry_id=command.ministry_id,
                start_at=command.start_at,
                end_at=command.end_at,
                is_mission_aligned=command.is_mission_aligned,
                billed_hours=total_billed,
                subtotal_amount=quote.subtotal_amount,
                discount_percent=quote.discount_percent,
                discount_amount=quote.discount_amount,
                surcharge_amount=quote.surcharge_amount,
                quoted_amount=quote.quoted_amount,
                currency=quote.currency,
            ),
        )
        await self._repository.replace_booking_rooms(booking_id, room_rows)
        await self._repository.replace_booking_slots(booking_id, slot_rows)
        return await self.get_booking_by_id(booking_id)

    @distributed_trace()
    async def create_booking(self, command: CreateBookingCommand) -> CreateIdResult:
        if command.end_at <= command.start_at:
            raise BadRequestException(detail="end_at must be after start_at")
        if not command.rooms:
            raise BadRequestException(detail="At least one room is required")
        operator_id = self._user_ctx.user_id if self._user_ctx else None
        if not operator_id:
            raise ForbiddenException(detail="Authenticated user required")
        booker_id = command.user_id or operator_id

        await self._validate_ministry_booking_gate(command.ministry_id, booker_id=booker_id)

        max_rooms = await self._rental_repository.get_policy_amount(
            RentalPolicySettingKey.MAX_ROOMS_PER_BOOKING,
            None,
        )
        max_rooms_int = int(max_rooms) if max_rooms is not None else 3
        if len(command.rooms) > max_rooms_int:
            raise BadRequestException(detail=f"At most {max_rooms_int} rooms per booking")

        local_tz = await self._setting_service.get_facility_timezone()
        for line in command.rooms:
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            await self._raise_if_room_unavailable(
                facility_id=line.facility_id,
                start_at=start_at,
                end_at=end_at,
                local_tz=local_tz,
            )

        quote_lines = []
        for line in command.rooms:
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            quote_lines.append(
                PreviewQuoteRoomLineCommand(
                    facility_id=line.facility_id,
                    billed_hours=self._billed_hours(start_at, end_at),
                )
            )

        quote = await self._pricing_service.preview_quote(
            PreviewQuoteCommand(
                booking_type=BookingType.ONE_TIME,
                is_mission_aligned=command.is_mission_aligned,
                currency="CAD",
                room_lines=quote_lines,
                surcharge_codes=command.surcharge_codes,
            )
        )

        booking_id = uuid4()
        primary_facility_id = command.rooms[0].facility_id
        total_billed = sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
        await self._repository.insert_booking(
            dict(
                id=booking_id,
                user_id=booker_id,
                facility_id=primary_facility_id,
                ministry_id=command.ministry_id,
                booking_type=BookingType.ONE_TIME.value,
                start_at=command.start_at,
                end_at=command.end_at,
                status=BookingStatus.CONFIRMED.value,
                is_mission_aligned=command.is_mission_aligned,
                billed_hours=total_billed,
                subtotal_amount=quote.subtotal_amount,
                discount_percent=quote.discount_percent,
                discount_amount=quote.discount_amount,
                surcharge_amount=quote.surcharge_amount,
                quoted_amount=quote.quoted_amount,
                currency=quote.currency,
                remark=command.remark,
            )
        )

        room_rows = []
        slot_rows = []
        for idx, line in enumerate(command.rooms):
            start_at = line.start_at or command.start_at
            end_at = line.end_at or command.end_at
            quoted_line = quote.room_lines[idx]
            room_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    sequence=line.sequence,
                    start_at=start_at,
                    end_at=end_at,
                    billed_hours=quoted_line.billed_hours,
                    rental_rate_name=quoted_line.rental_rate_name,
                    billing_unit=quoted_line.billing_unit,
                    unit_amount=quoted_line.unit_amount,
                    currency=quoted_line.currency,
                    applicability=quoted_line.applicability,
                    is_default=quoted_line.is_default,
                    line_subtotal=quoted_line.line_subtotal,
                )
            )
            slot_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
            )
        await self._repository.replace_booking_rooms(booking_id, room_rows)
        await self._repository.replace_booking_slots(booking_id, slot_rows)
        return CreateIdResult(id=booking_id)

    @distributed_trace()
    async def list_my_bookings(self) -> list[BookingListItemResult]:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        return await self._repository.list_user_bookings(user_id, self._resolved_locale_id())

    @distributed_trace()
    async def cancel_my_booking(self, booking_id: UUID, command: CancelBookingCommand) -> None:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        owner_id = await self._repository.get_user_id_for_booking(booking_id)
        if not owner_id:
            raise NotFoundException(detail="Booking not found")
        if owner_id != user_id:
            raise ForbiddenException(detail="Cannot cancel another user's booking")
        await self.cancel_booking(booking_id, command)

    async def _raise_if_room_unavailable(
        self,
        facility_id: UUID,
        start_at: datetime,
        end_at: datetime,
        local_tz: ZoneInfo,
        exclude_booking_id: Optional[UUID] = None,
    ) -> None:
        if await self._repository.has_confirmed_slot_overlap(
            facility_id=facility_id,
            start_at=start_at,
            end_at=end_at,
            exclude_booking_id=exclude_booking_id,
        ):
            raise ConflictErrorException(
                detail=f"Room {facility_id} has a scheduling conflict",
                error_code=BookingErrorCode.SCHEDULING_CONFLICT.value,
                context={"facility_id": str(facility_id)},
            )
        if await self._blackout_repository.has_blackout_overlap(
            facility_id=facility_id,
            start_at=start_at,
            end_at=end_at,
            tz=local_tz,
        ):
            raise BadRequestException(
                detail=f"Room {facility_id} is closed for the selected time",
                error_code=BookingErrorCode.ROOM_BLACKOUT.value,
                context={"facility_id": str(facility_id)},
            )

    async def _validate_ministry_booking_gate(
        self,
        ministry_id: Optional[UUID],
        booker_id: Optional[UUID] = None,
    ) -> None:
        if ministry_id is None:
            return
        status = await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(detail="Ministry must be active for booking")
        user_id = booker_id if booker_id is not None else (
            self._user_ctx.user_id if self._user_ctx else None
        )
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required for ministry booking")
        if not await self._ministry_repository.is_user_booking_member(ministry_id, user_id):
            raise ForbiddenException(detail="User is not a ministry owner")
