"""
Facility booking admin application service.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from portal.application.content.file_service import FileService
from portal.application.facility.booking_line_validation import (
    ResolvedBookingLine,
    envelope_interval,
    primary_facility_id,
    resolve_booking_lines,
    validate_booking_lines,
)
from portal.application.facility.commands import (
    BookingPagesQueryCommand,
    BookingRangeQueryCommand,
    BookingRoomLineCommand,
    CancelBookingCommand,
    CreateBookingCommand,
    MemberBrowseQueryCommand,
    MemberPreviewQuoteCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateBookingCommand,
    UpdateTitleCommand,
)
from portal.application.facility.discount_eligibility_service import is_mission_aligned_discount
from portal.application.facility.my_bookings import card_primary_facility_id, paginate_my_bookings_cards, project_my_bookings_cards
from portal.application.facility.participant_detail import assemble_participant_booking_detail
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.results import (
    BookingDetailResult,
    BookingPageResult,
    BookingRangeResult,
    MemberBrowseCardResult,
    MemberBrowsePageResult,
    ParticipantBookingDetailResult,
    PreviewQuoteResult,
    PreviewQuoteRoomLineResult,
)
from portal.application.org.results import CreateIdResult
from portal.application.system.setting_service import SettingService
from portal.domain.content.constants import FILE_RESOURCE_KIND_FACILITY_ROOM
from portal.domain.facility.cancellation_reason import InvalidMemberCancellationReason, normalize_member_cancellation_reason
from portal.domain.facility.constants import (
    BOOKING_RANGE_MAX_DAYS,
    ROOM_GALLERY_MAX_FILES,
    BookingErrorCode,
    BookingSlotStatus,
    BookingStatus,
    BookingType,
    FacilityErrorCode,
    RentalDiscountCode,
)
from portal.domain.facility.participant_detail import is_current_booking_participant
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.booking_draft_repository import BookingDraftRepository
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace

_PRICE_LOCKED_STATUSES = {BookingStatus.CONFIRMED.value, BookingStatus.PENDING_PAYMENT.value}


class BookingService:
    """Admin booking operations (list, detail, cancel, update)."""

    def __init__(
        self,
        booking_repository: BookingRepository,
        pricing_service: PricingService,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
        booking_draft_repository: BookingDraftRepository,
        file_service: FileService,
    ):
        self._repository = booking_repository
        self._pricing_service = pricing_service
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._booking_draft_repository = booking_draft_repository
        self._file_service = file_service
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

    @staticmethod
    def _quote_from_existing(existing: BookingDetailResult) -> PreviewQuoteResult:
        room_lines = [
            PreviewQuoteRoomLineResult(
                facility_id=line.facility_id,
                billed_hours=line.billed_hours or Decimal("0"),
                rental_rate_name=line.rental_rate_name or "",
                billing_unit=line.billing_unit or "",
                unit_amount=line.unit_amount or Decimal("0"),
                currency=line.currency or existing.currency or "CAD",
                applicability=line.applicability,
                is_default=bool(line.is_default),
                line_subtotal=line.line_subtotal or Decimal("0"),
            )
            for line in existing.rooms
        ]
        return PreviewQuoteResult(
            subtotal_amount=existing.subtotal_amount or Decimal("0"),
            discount_code=RentalDiscountCode.MISSION_ALIGNED.value if existing.is_mission_aligned else None,
            discount_percent=existing.discount_percent or Decimal("0"),
            discount_amount=existing.discount_amount or Decimal("0"),
            surcharge_amount=existing.surcharge_amount or Decimal("0"),
            quoted_amount=existing.quoted_amount or Decimal("0"),
            currency=existing.currency or "CAD",
            room_lines=room_lines,
        )

    async def _raise_if_too_many_booking_lines(self, rooms: list[BookingRoomLineCommand]) -> None:
        max_lines = await self._setting_service.get_max_booking_lines()
        if len(rooms) > max_lines:
            raise BadRequestException(detail=f"At most {max_lines} rooms per booking", error_code=FacilityErrorCode.BOOKING_MAX_ROOMS.value)

    @distributed_trace()
    async def get_booking_pages(self, command: BookingPagesQueryCommand) -> BookingPageResult:
        items, count = await self._repository.fetch_pages(command, self._resolved_locale_id())
        return BookingPageResult(page=command.page, page_size=command.page_size, total=count, items=items)

    @distributed_trace()
    async def get_booking_range(self, command: BookingRangeQueryCommand) -> BookingRangeResult:
        if command.date_to <= command.date_from:
            raise BadRequestException(detail="date_to must be after date_from", error_code=FacilityErrorCode.BOOKING_INVALID_TIME_RANGE.value)
        if command.date_to - command.date_from > timedelta(days=BOOKING_RANGE_MAX_DAYS):
            raise BadRequestException(
                detail=f"Booking range window must be at most {BOOKING_RANGE_MAX_DAYS} days", error_code=FacilityErrorCode.BOOKING_RANGE_WINDOW_TOO_LARGE.value
            )
        items = await self._repository.fetch_range(command, self._resolved_locale_id())
        return BookingRangeResult(items=items)

    @distributed_trace()
    async def get_booking_by_id(self, booking_id: UUID) -> BookingDetailResult:
        row = await self._repository.get_detail(booking_id, self._resolved_locale_id())
        if not row:
            raise NotFoundException(detail="Booking not found", error_code=FacilityErrorCode.BOOKING_NOT_FOUND.value, context={"booking_id": str(booking_id)})
        return row

    @distributed_trace()
    async def cancel_booking(self, booking_id: UUID, command: CancelBookingCommand) -> None:
        if not await self._repository.exists_by_id(booking_id):
            raise NotFoundException(detail="Booking not found", error_code=FacilityErrorCode.BOOKING_NOT_FOUND.value, context={"booking_id": str(booking_id)})
        cancelled_by_id = self._user_ctx.user_id if self._user_ctx else None
        cancel_slots = command.scope != "series"
        await self._repository.cancel_booking(
            booking_id=booking_id, cancelled_by_id=cancelled_by_id, cancel_reason=command.cancel_reason, cancel_slots=cancel_slots
        )

    @distributed_trace()
    async def update_booking(self, booking_id: UUID, command: UpdateBookingCommand) -> BookingDetailResult:
        if not command.rooms:
            raise BadRequestException(detail="At least one room is required", error_code=FacilityErrorCode.BOOKING_ROOMS_REQUIRED.value)

        await self._validate_ministry_booking_gate(command.ministry_id)

        meta = await self._repository.get_booking_type_and_flags(booking_id)
        if not meta:
            raise NotFoundException(detail="Booking not found", error_code=FacilityErrorCode.BOOKING_NOT_FOUND.value, context={"booking_id": str(booking_id)})

        await self._raise_if_too_many_booking_lines(command.rooms)

        local_tz = await self._setting_service.get_facility_timezone()
        resolved_lines = resolve_booking_lines(command.rooms, command.start_at, command.end_at)
        validate_booking_lines(resolved_lines, local_tz)
        header_start, header_end = envelope_interval(resolved_lines)

        for line in resolved_lines:
            await self._raise_if_room_unavailable(
                facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, local_tz=local_tz, exclude_booking_id=booking_id
            )

        quote_lines = [
            PreviewQuoteRoomLineCommand(facility_id=line.facility_id, billed_hours=self._billed_hours(line.start_at, line.end_at)) for line in resolved_lines
        ]

        booking_type = BookingType(meta.booking_type)
        currency = meta.currency or "CAD"
        if meta.status in _PRICE_LOCKED_STATUSES:
            existing = await self._repository.get_detail(booking_id, self._resolved_locale_id())
            if existing is None:
                raise NotFoundException(
                    detail="Booking not found", error_code=FacilityErrorCode.BOOKING_NOT_FOUND.value, context={"booking_id": str(booking_id)}
                )
            quote = self._quote_from_existing(existing)
        else:
            booker_id = await self._repository.get_user_id_for_booking(booking_id)
            quote = await self._pricing_service.preview_quote(
                PreviewQuoteCommand(
                    booking_type=booking_type,
                    currency=currency,
                    room_lines=quote_lines,
                    surcharge_codes=command.surcharge_codes,
                    ministry_id=command.ministry_id,
                    booker_id=booker_id,
                )
            )

        primary_facility_id_value = primary_facility_id(resolved_lines)
        room_rows = []
        slot_rows = []
        for idx, line in enumerate(resolved_lines):
            quoted_line = quote.room_lines[idx] if idx < len(quote.room_lines) else None
            room_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    sequence=line.sequence,
                    start_at=line.start_at,
                    end_at=line.end_at,
                    billed_hours=quoted_line.billed_hours if quoted_line else self._billed_hours(line.start_at, line.end_at),
                    rental_rate_name=quoted_line.rental_rate_name if quoted_line else "",
                    billing_unit=quoted_line.billing_unit if quoted_line else "",
                    unit_amount=quoted_line.unit_amount if quoted_line else Decimal("0"),
                    currency=quoted_line.currency if quoted_line else quote.currency,
                    applicability=quoted_line.applicability if quoted_line else None,
                    is_default=quoted_line.is_default if quoted_line else False,
                    line_subtotal=quoted_line.line_subtotal if quoted_line else Decimal("0"),
                )
            )
            slot_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    start_at=line.start_at,
                    end_at=line.end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
            )

        total_billed = sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
        await self._repository.update_booking_header(
            booking_id,
            dict(
                facility_id=primary_facility_id_value,
                ministry_id=command.ministry_id,
                start_at=header_start,
                end_at=header_end,
                is_mission_aligned=is_mission_aligned_discount(quote.discount_code),
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
        if not command.rooms:
            raise BadRequestException(detail="At least one room is required", error_code=FacilityErrorCode.BOOKING_ROOMS_REQUIRED.value)
        operator_id = self._user_ctx.user_id if self._user_ctx else None
        if not operator_id:
            raise ForbiddenException(detail="Authenticated user required")
        booker_id = command.user_id or operator_id

        await self._validate_ministry_booking_gate(command.ministry_id, booker_id=booker_id)

        await self._raise_if_too_many_booking_lines(command.rooms)

        local_tz = await self._setting_service.get_facility_timezone()
        resolved_lines = resolve_booking_lines(command.rooms, command.start_at, command.end_at)
        validate_booking_lines(resolved_lines, local_tz)
        header_start, header_end = envelope_interval(resolved_lines)

        for line in resolved_lines:
            await self._raise_if_room_unavailable(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, local_tz=local_tz)

        quote_lines = [
            PreviewQuoteRoomLineCommand(facility_id=line.facility_id, billed_hours=self._billed_hours(line.start_at, line.end_at)) for line in resolved_lines
        ]

        quote = await self._pricing_service.preview_quote(
            PreviewQuoteCommand(
                booking_type=BookingType.ONE_TIME,
                currency="CAD",
                room_lines=quote_lines,
                surcharge_codes=command.surcharge_codes,
                ministry_id=command.ministry_id,
                booker_id=booker_id,
            )
        )

        booking_id = uuid4()
        primary_facility_id_value = primary_facility_id(resolved_lines)
        total_billed = sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
        await self._repository.insert_booking(
            dict(
                id=booking_id,
                user_id=booker_id,
                facility_id=primary_facility_id_value,
                ministry_id=command.ministry_id,
                booking_type=BookingType.ONE_TIME.value,
                start_at=header_start,
                end_at=header_end,
                status=BookingStatus.CONFIRMED.value,
                is_mission_aligned=is_mission_aligned_discount(quote.discount_code),
                billed_hours=total_billed,
                subtotal_amount=quote.subtotal_amount,
                discount_percent=quote.discount_percent,
                discount_amount=quote.discount_amount,
                surcharge_amount=quote.surcharge_amount,
                quoted_amount=quote.quoted_amount,
                currency=quote.currency,
                remark=command.remark,
                title=command.title,
            )
        )

        room_rows = []
        slot_rows = []
        for idx, line in enumerate(resolved_lines):
            quoted_line = quote.room_lines[idx]
            room_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=line.facility_id,
                    sequence=line.sequence,
                    start_at=line.start_at,
                    end_at=line.end_at,
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
                    start_at=line.start_at,
                    end_at=line.end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
            )
        await self._repository.replace_booking_rooms(booking_id, room_rows)
        await self._repository.replace_booking_slots(booking_id, slot_rows)

        if command.booking_draft_id is not None:
            # Ownership check guards against one booker deleting another member's Draft by id; a mismatch
            # or already-gone Draft is treated like any other abandoned Draft and left alone, not an error.
            draft = await self._booking_draft_repository.get_detail(command.booking_draft_id)
            if draft and draft.user_id == booker_id:
                await self._booking_draft_repository.delete_draft(command.booking_draft_id)

        return CreateIdResult(id=booking_id)

    @distributed_trace()
    async def browse_my_bookings(self, command: MemberBrowseQueryCommand, now: Optional[datetime] = None) -> MemberBrowsePageResult:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        browse_now = now or datetime.now(timezone.utc)
        locale_id = self._resolved_locale_id()
        owned = await self._ministry_repository.list_owned_active(user_id, locale_id)
        ministry_ids = [item.id for item in owned]
        rows = await self._repository.list_participant_bookings(user_id, ministry_ids, locale_id)
        facility_tz = await self._setting_service.get_facility_timezone()
        cards = project_my_bookings_cards(rows, section=command.section, user_id=user_id, now=browse_now, facility_tz=facility_tz)
        page_items, total = paginate_my_bookings_cards(cards, command.page, command.page_size)
        page_items = await self._attach_browse_photos(page_items)
        return MemberBrowsePageResult(page=command.page, page_size=command.page_size, total=total, section=command.section.value, items=page_items)

    async def _attach_browse_photos(self, cards: list[MemberBrowseCardResult]) -> list[MemberBrowseCardResult]:
        facility_ids = [facility_id for facility_id in (card_primary_facility_id(card) for card in cards) if facility_id is not None]
        urls_by_room = await self._file_service.get_signed_urls_by_resource_ids(facility_ids, resource_name=FILE_RESOURCE_KIND_FACILITY_ROOM)
        attached: list[MemberBrowseCardResult] = []
        for card in cards:
            facility_id = card_primary_facility_id(card)
            photo_urls = urls_by_room.get(facility_id, [])[:ROOM_GALLERY_MAX_FILES] if facility_id else []
            attached.append(card.model_copy(update={"photo_urls": photo_urls}))
        return attached

    async def _owned_ministry_ids(self, user_id: UUID) -> list[UUID]:
        owned = await self._ministry_repository.list_owned_active(user_id, self._resolved_locale_id())
        return [item.id for item in owned]

    async def _require_participant_booking(self, booking_id: UUID, user_id: UUID) -> BookingDetailResult:
        row = await self._repository.get_detail(booking_id, self._resolved_locale_id())
        if not row or not is_current_booking_participant(
            viewer_id=user_id, booker_id=row.user_id, ministry_id=row.ministry_id, owned_ministry_ids=await self._owned_ministry_ids(user_id)
        ):
            raise NotFoundException(detail="Booking not found", error_code=FacilityErrorCode.BOOKING_NOT_FOUND.value, context={"booking_id": str(booking_id)})
        return row

    @staticmethod
    def _require_member_cancellation_reason(cancel_reason: Optional[str]) -> str:
        try:
            return normalize_member_cancellation_reason(cancel_reason or "")
        except InvalidMemberCancellationReason as exc:
            raise BadRequestException(detail=str(exc), error_code=FacilityErrorCode.BOOKING_CANCEL_REASON_INVALID.value) from exc

    @distributed_trace()
    async def update_my_booking_title(self, booking_id: UUID, command: UpdateTitleCommand) -> ParticipantBookingDetailResult:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        row = await self._require_participant_booking(booking_id, user_id)
        if row.user_id != user_id:
            raise ForbiddenException(detail="Cannot update another user's booking")
        await self._repository.update_booking_header(booking_id, dict(title=command.title))
        return await self.get_my_booking_by_id(booking_id)

    @distributed_trace()
    async def cancel_my_booking(self, booking_id: UUID, command: CancelBookingCommand) -> None:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        row = await self._require_participant_booking(booking_id, user_id)
        if row.user_id != user_id:
            raise ForbiddenException(detail="Cannot cancel another user's booking")
        cancel_reason = self._require_member_cancellation_reason(command.cancel_reason)
        await self.cancel_booking(booking_id, CancelBookingCommand(scope=command.scope, cancel_reason=cancel_reason))

    @distributed_trace()
    async def get_my_booking_by_id(self, booking_id: UUID, now: Optional[datetime] = None) -> ParticipantBookingDetailResult:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        row = await self._require_participant_booking(booking_id, user_id)
        browse_now = now or datetime.now(timezone.utc)
        facility_tz = await self._setting_service.get_facility_timezone()
        facility_ids = [line.facility_id for line in row.rooms]
        urls_by_room = await self._file_service.get_signed_urls_by_resource_ids(facility_ids, resource_name=FILE_RESOURCE_KIND_FACILITY_ROOM)
        return assemble_participant_booking_detail(row, viewer_id=user_id, now=browse_now, facility_tz=facility_tz, photo_urls_by_room=urls_by_room)

    @distributed_trace()
    async def preview_quote_for_member(self, command: MemberPreviewQuoteCommand) -> PreviewQuoteResult:
        await self._validate_ministry_booking_gate(command.ministry_id)

        resolved_lines = [
            ResolvedBookingLine(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=index)
            for index, line in enumerate(command.lines)
        ]
        local_tz = await self._setting_service.get_facility_timezone()
        validate_booking_lines(resolved_lines, local_tz)

        quote_lines = [
            PreviewQuoteRoomLineCommand(facility_id=line.facility_id, billed_hours=self._billed_hours(line.start_at, line.end_at)) for line in resolved_lines
        ]

        return await self._pricing_service.preview_quote(
            PreviewQuoteCommand(
                booking_type=BookingType.ONE_TIME,
                currency=command.currency,
                room_lines=quote_lines,
                surcharge_codes=command.surcharge_codes,
                ministry_id=command.ministry_id,
                booker_id=self._user_ctx.user_id if self._user_ctx else None,
            )
        )

    async def _raise_if_room_unavailable(
        self, facility_id: UUID, start_at: datetime, end_at: datetime, local_tz: ZoneInfo, exclude_booking_id: Optional[UUID] = None
    ) -> None:
        if await self._repository.has_confirmed_slot_overlap(facility_id=facility_id, start_at=start_at, end_at=end_at, exclude_booking_id=exclude_booking_id):
            raise ConflictErrorException(
                detail=f"Room {facility_id} has a scheduling conflict",
                error_code=BookingErrorCode.SCHEDULING_CONFLICT.value,
                context={"facility_id": str(facility_id)},
            )
        if await self._blackout_repository.has_blackout_overlap(facility_id=facility_id, start_at=start_at, end_at=end_at, tz=local_tz):
            raise BadRequestException(
                detail=f"Room {facility_id} is closed for the selected time",
                error_code=BookingErrorCode.ROOM_BLACKOUT.value,
                context={"facility_id": str(facility_id)},
            )

    async def _validate_ministry_booking_gate(self, ministry_id: Optional[UUID], booker_id: Optional[UUID] = None) -> None:
        if ministry_id is None:
            return
        status = await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(
                detail="Ministry must be active for booking",
                error_code=FacilityErrorCode.BOOKING_MINISTRY_INACTIVE.value,
                context={"ministry_id": str(ministry_id)},
            )
        user_id = booker_id if booker_id is not None else (self._user_ctx.user_id if self._user_ctx else None)
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required for ministry booking")
        if not await self._ministry_repository.is_user_booking_member(ministry_id, user_id):
            raise ForbiddenException(detail="User is not a ministry owner")
