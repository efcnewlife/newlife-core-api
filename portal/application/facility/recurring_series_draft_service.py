"""
Recurring Series Draft application service.
"""

from typing import Optional
from uuid import UUID, uuid4

from portal.application.facility.commands import (
    BookingRoomLineCommand,
    CreateRecurringBookingSeriesCommand,
    CreateRecurringSeriesDraftCommand,
    UpdateRecurringSeriesDraftCommand,
)
from portal.application.facility.discount_eligibility_service import is_mission_aligned_discount
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import (
    RecurringBookingSeriesResult,
    RecurringSeriesDraftDetailResult,
    RecurringSeriesDraftResult,
    RecurringSeriesDraftStoredRoomResult,
)
from portal.application.org.results import CreateIdResult
from portal.domain.facility.constants import FacilityErrorCode
from portal.exceptions.responses import ConflictErrorException, ForbiddenException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.recurring_series_draft_repository import RecurringSeriesDraftRepository
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class RecurringSeriesDraftService:
    """Create, review, confirm, and clear member Recurring Series Drafts; never reserves rooms."""

    def __init__(self, series_draft_repository: RecurringSeriesDraftRepository, recurring_booking_service: RecurringBookingService):
        self._repository = series_draft_repository
        self._recurring_booking_service = recurring_booking_service
        self._user_ctx: Optional[UserContext] = get_user_context()

    def _authenticated_user_id(self) -> UUID:
        user_id = self._user_ctx.user_id if self._user_ctx else None
        if not user_id:
            raise ForbiddenException(detail="Authenticated user required")
        return user_id

    async def _get_owned_draft_or_404(self, series_draft_id: UUID, user_id: UUID) -> RecurringSeriesDraftDetailResult:
        row = await self._repository.get_detail(series_draft_id)
        if not row or row.user_id != user_id:
            raise NotFoundException(
                detail="Recurring Series Draft not found",
                error_code=FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value,
                context={"series_draft_id": str(series_draft_id)},
            )
        return row

    @staticmethod
    def _to_series_command(command: CreateRecurringSeriesDraftCommand) -> CreateRecurringBookingSeriesCommand:
        return CreateRecurringBookingSeriesCommand(
            title=command.title,
            ministry_id=command.ministry_id,
            first_occurrence_date=command.first_occurrence_date,
            last_occurrence_date=command.last_occurrence_date,
            local_start_time=command.local_start_time,
            local_end_time=command.local_end_time,
            rooms=command.rooms,
            surcharge_codes=command.surcharge_codes,
            remark=command.remark,
            excluded_dates=command.excluded_dates,
        )

    @staticmethod
    def _stored_to_series_command(row: RecurringSeriesDraftDetailResult) -> CreateRecurringBookingSeriesCommand:
        return CreateRecurringBookingSeriesCommand(
            title=row.title,
            ministry_id=row.ministry_id,
            first_occurrence_date=row.first_occurrence_date,
            last_occurrence_date=row.last_occurrence_date,
            local_start_time=row.local_start_time,
            local_end_time=row.local_end_time,
            rooms=[BookingRoomLineCommand(facility_id=room.facility_id, sequence=room.sequence) for room in row.rooms],
            surcharge_codes=row.surcharge_codes,
            remark=row.remark,
            excluded_dates=row.excluded_dates,
        )

    @staticmethod
    def _header_payload(draft_id: UUID, user_id: UUID, command: CreateRecurringSeriesDraftCommand) -> dict:
        return dict(
            id=draft_id,
            user_id=user_id,
            title=command.title,
            ministry_id=command.ministry_id,
            first_occurrence_date=command.first_occurrence_date,
            last_occurrence_date=command.last_occurrence_date,
            local_start_time=command.local_start_time,
            local_end_time=command.local_end_time,
            is_mission_aligned=False,
            remark=command.remark,
            surcharge_codes=list(command.surcharge_codes),
            excluded_dates=list(command.excluded_dates),
        )

    @staticmethod
    def _room_rows(draft_id: UUID, command: CreateRecurringSeriesDraftCommand) -> list[dict]:
        return [dict(id=uuid4(), series_draft_id=draft_id, facility_id=room.facility_id, sequence=room.sequence) for room in command.rooms]

    async def _to_draft_result(self, row: RecurringSeriesDraftDetailResult) -> RecurringSeriesDraftResult:
        evaluation = await self._recurring_booking_service.evaluate_proposal(self._stored_to_series_command(row))
        return RecurringSeriesDraftResult(
            id=row.id,
            title=row.title,
            ministry_id=row.ministry_id,
            first_occurrence_date=row.first_occurrence_date,
            last_occurrence_date=row.last_occurrence_date,
            local_start_time=row.local_start_time,
            local_end_time=row.local_end_time,
            is_mission_aligned=is_mission_aligned_discount(evaluation.discount_code),
            remark=row.remark,
            surcharge_codes=row.surcharge_codes,
            excluded_dates=row.excluded_dates,
            rooms=[RecurringSeriesDraftStoredRoomResult(facility_id=room.facility_id, sequence=room.sequence) for room in row.rooms],
            conflicts=evaluation.conflicts,
            is_confirmable=evaluation.is_confirmable,
            invalidity_code=evaluation.invalidity_code,
            invalidity_detail=evaluation.invalidity_detail,
            quoted_amount=evaluation.quoted_amount,
            subtotal_amount=evaluation.subtotal_amount,
            discount_percent=evaluation.discount_percent,
            discount_amount=evaluation.discount_amount,
            surcharge_amount=evaluation.surcharge_amount,
            currency=evaluation.currency,
            occurrence_count=evaluation.occurrence_count,
            pending_payment_hold_hours=evaluation.pending_payment_hold_hours,
            payment_hold_expires_at=evaluation.payment_hold_expires_at,
        )

    @distributed_trace()
    async def create_draft(self, command: CreateRecurringSeriesDraftCommand) -> CreateIdResult:
        user_id = self._authenticated_user_id()
        await self._recurring_booking_service.preview_conflicts(self._to_series_command(command))
        draft_id = uuid4()
        await self._repository.insert_draft(self._header_payload(draft_id, user_id, command))
        await self._repository.insert_rooms(self._room_rows(draft_id, command))
        return CreateIdResult(id=draft_id)

    @distributed_trace()
    async def update_draft(self, series_draft_id: UUID, command: UpdateRecurringSeriesDraftCommand) -> RecurringSeriesDraftResult:
        user_id = self._authenticated_user_id()
        await self._get_owned_draft_or_404(series_draft_id, user_id)
        await self._recurring_booking_service.preview_conflicts(self._to_series_command(command))
        header = self._header_payload(series_draft_id, user_id, command)
        header.pop("id")
        header.pop("user_id")
        await self._repository.update_header(series_draft_id, header)
        await self._repository.replace_rooms(series_draft_id, self._room_rows(series_draft_id, command))
        return await self.get_draft(series_draft_id)

    @distributed_trace()
    async def get_draft(self, series_draft_id: UUID) -> RecurringSeriesDraftResult:
        user_id = self._authenticated_user_id()
        row = await self._get_owned_draft_or_404(series_draft_id, user_id)
        return await self._to_draft_result(row)

    @distributed_trace()
    async def confirm_draft(self, series_draft_id: UUID) -> RecurringBookingSeriesResult:
        user_id = self._authenticated_user_id()
        row = await self._get_owned_draft_or_404(series_draft_id, user_id)
        command = self._stored_to_series_command(row)
        evaluation = await self._recurring_booking_service.evaluate_proposal(command)
        if not evaluation.is_confirmable:
            raise ConflictErrorException(
                detail=evaluation.invalidity_detail or "Recurring Series Draft is not confirmable",
                error_code=FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_CONFIRMABLE.value,
                context={
                    "series_draft_id": str(series_draft_id),
                    "invalidity_code": evaluation.invalidity_code,
                    "conflicts": [item.model_dump(mode="json") for item in evaluation.conflicts],
                },
            )
        result = await self._recurring_booking_service.create_series(command)
        await self._repository.delete_draft(series_draft_id)
        return result

    @distributed_trace()
    async def delete_all_my_drafts(self) -> None:
        user_id = self._authenticated_user_id()
        await self._repository.delete_all_for_user(user_id)
