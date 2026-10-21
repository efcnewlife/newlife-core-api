"""
Booking Draft application service (ADR 0018).
"""

from datetime import date as DateType
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID, uuid4

from portal.application.facility.booking_line_validation import ResolvedBookingLine, validate_booking_lines
from portal.application.facility.commands import (
    BookingDraftLineCommand,
    CreateBookingDraftCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
    UpdateBookingDraftCommand,
)
from portal.application.facility.one_time_override import evaluate_one_time_occupancy, load_ministry_proposal_context, one_time_proposal
from portal.application.facility.opening_hours import member_interval_within_opening_hours
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.priority_override import issue_override_review_token, override_review_secret
from portal.application.facility.results import BookingConflictResult, BookingDraftDetailResult, BookingDraftLineResult, BookingDraftResult
from portal.application.org.results import CreateIdResult
from portal.application.system.setting_service import SettingService
from portal.domain.facility.constants import BookingType, FacilityErrorCode, RecurringConflictKind
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.booking_draft_repository import BookingDraftRepository
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.facility.room_slot_template_repository import RoomSlotTemplateRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class BookingDraftService:
    """Create and fetch member Booking Drafts; price and availability are always computed live."""

    def __init__(
        self,
        booking_draft_repository: BookingDraftRepository,
        booking_repository: BookingRepository,
        room_blackout_repository: RoomBlackoutRepository,
        pricing_service: PricingService,
        setting_service: SettingService,
        room_slot_template_repository: RoomSlotTemplateRepository,
        ministry_repository: MinistryRepository,
        now_utc: Optional[Callable[[], datetime]] = None,
        review_secret: Optional[bytes] = None,
    ):
        self._repository = booking_draft_repository
        self._booking_repository = booking_repository
        self._blackout_repository = room_blackout_repository
        self._pricing_service = pricing_service
        self._setting_service = setting_service
        self._slot_template_repository = room_slot_template_repository
        self._ministry_repository = ministry_repository
        self._now_utc = now_utc or (lambda: datetime.now(timezone.utc))
        self._review_secret = review_secret or override_review_secret()
        self._req_ctx: Optional[RequestContext] = get_request_context()
        self._user_ctx: Optional[UserContext] = get_user_context()

    @staticmethod
    def _billed_hours(start_at: datetime, end_at: datetime) -> Decimal:
        delta = end_at - start_at
        hours = Decimal(str(delta.total_seconds())) / Decimal("3600")
        return hours.quantize(Decimal("0.01"))

    def _authenticated_user_id(self) -> UUID:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        return user_id

    async def _get_owned_draft_or_404(self, booking_draft_id: UUID, user_id: UUID) -> BookingDraftDetailResult:
        row = await self._repository.get_detail(booking_draft_id)
        if not row or row.user_id != user_id:
            raise NotFoundException(
                detail="Booking draft not found",
                error_code=FacilityErrorCode.BOOKING_DRAFT_NOT_FOUND.value,
                context={"booking_draft_id": str(booking_draft_id)},
            )
        return row

    async def _resolve_and_validate_lines(self, lines: list[BookingDraftLineCommand]) -> tuple[list[ResolvedBookingLine], DateType]:
        if not lines:
            raise BadRequestException(detail="At least one line is required", error_code=FacilityErrorCode.BOOKING_ROOMS_REQUIRED.value)

        max_lines = await self._setting_service.get_max_booking_lines()
        if len(lines) > max_lines:
            raise BadRequestException(detail=f"At most {max_lines} lines per booking", error_code=FacilityErrorCode.BOOKING_MAX_ROOMS.value)

        local_tz = await self._setting_service.get_facility_timezone()
        resolved_lines = [
            ResolvedBookingLine(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence) for line in lines
        ]
        validate_booking_lines(resolved_lines, local_tz)
        draft_date = resolved_lines[0].start_at.astimezone(local_tz).date()
        return resolved_lines, draft_date

    @distributed_trace()
    async def create_draft(self, command: CreateBookingDraftCommand) -> CreateIdResult:
        user_id = self._authenticated_user_id()
        resolved_lines, draft_date = await self._resolve_and_validate_lines(command.lines)

        draft_id = uuid4()
        await self._repository.insert_draft(dict(id=draft_id, user_id=user_id, title=command.title, date=draft_date, ministry_id=command.ministry_id))
        line_rows = [
            dict(id=uuid4(), booking_draft_id=draft_id, facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence)
            for line in resolved_lines
        ]
        await self._repository.insert_lines(line_rows)
        return CreateIdResult(id=draft_id)

    @distributed_trace()
    async def update_draft(self, booking_draft_id: UUID, command: UpdateBookingDraftCommand) -> BookingDraftResult:
        """Replace a Draft's lines in place; concurrent PATCHes are last-write-wins (no version/merge)."""
        user_id = self._authenticated_user_id()
        await self._get_owned_draft_or_404(booking_draft_id, user_id)

        resolved_lines, draft_date = await self._resolve_and_validate_lines(command.lines)

        await self._repository.update_header(booking_draft_id, dict(title=command.title, date=draft_date, ministry_id=command.ministry_id))
        line_rows = [
            dict(
                id=uuid4(), booking_draft_id=booking_draft_id, facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence
            )
            for line in resolved_lines
        ]
        await self._repository.replace_lines(booking_draft_id, line_rows)
        return await self.get_draft(booking_draft_id)

    @distributed_trace()
    async def get_draft(self, booking_draft_id: UUID) -> BookingDraftResult:
        """Evaluate the owned Draft live; never reserves, displaces, or notifies."""
        user_id = self._authenticated_user_id()
        row = await self._get_owned_draft_or_404(booking_draft_id, user_id)

        local_tz = await self._setting_service.get_facility_timezone()
        resolved_lines = [
            ResolvedBookingLine(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, sequence=line.sequence) for line in row.lines
        ]
        context = await load_ministry_proposal_context(self._ministry_repository, row.ministry_id, user_id) if row.ministry_id else None
        evaluation = await evaluate_one_time_occupancy(
            lines=resolved_lines,
            context=context,
            now_utc=self._now_utc(),
            local_tz=local_tz,
            booking_repository=self._booking_repository,
            ministry_repository=self._ministry_repository,
            allow_override=True,
            locale_id=self._req_ctx.resolved_locale_id if self._req_ctx else None,
        )
        conflicts = list(evaluation.conflicts)
        line_results: list[BookingDraftLineResult] = []
        quote_lines: list[PreviewQuoteRoomLineCommand] = []
        for line in row.lines:
            day = line.start_at.astimezone(local_tz).date()
            templates = await self._slot_template_repository.list_active_for_day(line.facility_id, day.weekday())
            outside_opening = not member_interval_within_opening_hours(line.start_at, line.end_at, templates, local_tz)
            is_blackout = await self._blackout_repository.has_blackout_overlap(
                facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, tz=local_tz
            )
            is_occupied = await self._booking_repository.has_confirmed_slot_overlap(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at)
            for is_closed, kind in ((is_blackout, RecurringConflictKind.BLACKOUT), (outside_opening, RecurringConflictKind.OPENING_HOURS)):
                if is_closed:
                    conflicts.append(BookingConflictResult(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, kind=kind.value))
            line_results.append(
                BookingDraftLineResult(
                    facility_id=line.facility_id,
                    start_at=line.start_at,
                    end_at=line.end_at,
                    sequence=line.sequence,
                    is_available=not (is_occupied or is_blackout or outside_opening),
                )
            )
            quote_lines.append(PreviewQuoteRoomLineCommand(facility_id=line.facility_id, billed_hours=self._billed_hours(line.start_at, line.end_at)))

        quote = await self._pricing_service.preview_quote(
            PreviewQuoteCommand(booking_type=BookingType.ONE_TIME, currency="CAD", room_lines=quote_lines, ministry_id=row.ministry_id, booker_id=user_id)
        )

        is_confirmable = bool(resolved_lines) and not conflicts and (row.ministry_id is None or context is not None)
        override_review_token = None
        if is_confirmable and evaluation.impacts:
            override_review_token = issue_override_review_token(
                booker_id=user_id,
                ministry_id=row.ministry_id,
                proposal=one_time_proposal(resolved_lines),
                impacts=evaluation.impacts,
                secret=self._review_secret,
            )

        return BookingDraftResult(
            id=booking_draft_id,
            title=row.title,
            date=row.date,
            ministry_id=row.ministry_id,
            lines=line_results,
            subtotal_amount=quote.subtotal_amount,
            discount_percent=quote.discount_percent,
            discount_amount=quote.discount_amount,
            surcharge_amount=quote.surcharge_amount,
            quoted_amount=quote.quoted_amount,
            currency=quote.currency,
            is_confirmable=is_confirmable,
            conflicts=conflicts,
            override_impacts=evaluation.impacts,
            override_review_token=override_review_token,
        )

    @distributed_trace()
    async def delete_all_my_drafts(self) -> None:
        """Delete every Booking Draft owned by the authenticated member; a no-op if they have none."""
        user_id = self._authenticated_user_id()
        await self._repository.delete_all_for_user(user_id)
