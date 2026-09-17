"""
Recurring Booking Series application service.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Callable, NamedTuple, Optional, Protocol
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from portal.application.auth.user_read_service import UserReadService
from portal.application.facility.booking_line_validation import ResolvedBookingLine, primary_facility_id, validate_booking_lines
from portal.application.facility.commands import (
    CancelRecurringBookingSeriesCommand,
    CreateRecurringBookingSeriesCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
)
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.recurring_override_mail_content import resolve_bilingual_activity_names
from portal.application.facility.results import (
    BlackoutImpactOccurrenceResult,
    BlackoutImpactResult,
    PendingPaymentExpirySweepResult,
    PendingPaymentSeriesListResult,
    RecurringBookingConflictResult,
    RecurringBookingOccurrenceResult,
    RecurringBookingPreviewResult,
    RecurringBookingSeriesResult,
    RecurringOccupyingBookingResult,
    RecurringOverrideNotification,
    RecurringOverrideNotificationItem,
    RecurringPaymentHoldExpiryNotification,
    RoomBlackoutResult,
)
from portal.application.system.setting_service import SettingService
from portal.domain.facility.constants import (
    CHURCH_EMAIL_DOMAIN,
    PENDING_PAYMENT_HOLD_EXPIRED_REASON,
    BookingErrorCode,
    BookingSlotStatus,
    BookingStatus,
    BookingType,
    FacilityErrorCode,
    OverrideOutcome,
    RecurringCancellationScope,
    RecurringConflictKind,
)
from portal.domain.facility.recurring import (
    is_church_email,
    is_pending_payment_hold_active,
    is_within_availability_window,
    localize_wall_time,
    opening_date_for_period,
    sunday_week_start,
    use_period_for_date,
    weekly_occurrence_dates,
)
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.recurring_booking_repository import RecurringBookingRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.request_context import RequestContext, get_request_context
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.logger import logger
from portal.libs.tracing.distributed_trace import distributed_trace


class _PreparedOccurrence(NamedTuple):
    occurrence_date: date
    start_at: datetime
    end_at: datetime


class _PreparedSeries(NamedTuple):
    booker_id: UUID
    operator_id: UUID
    local_tz: ZoneInfo
    now_utc: datetime
    occurrences: list[_PreparedOccurrence]
    is_priority: bool
    ministry_name: Optional[str]
    ministry_name_zh: Optional[str]


class RecurringOverrideNotifierPort(Protocol):
    """Send Priority Ministry override notifications after Series create."""

    async def notify_priority_override(self, notification: RecurringOverrideNotification) -> None: ...


class RecurringExpiryNotifierPort(Protocol):
    """Send Pending-payment hold expiry mail to the Booker."""

    async def notify_payment_hold_expired(self, notification: RecurringPaymentHoldExpiryNotification) -> None: ...


class NullRecurringOverrideNotifier:
    """No-op notifier used when mail is not wired."""

    async def notify_priority_override(self, notification: RecurringOverrideNotification) -> None:
        return None


class NullRecurringExpiryNotifier:
    """No-op expiry notifier used when mail is not wired."""

    async def notify_payment_hold_expired(self, notification: RecurringPaymentHoldExpiryNotification) -> None:
        return None


_LIVE_OCCURRENCE_STATUSES = {BookingStatus.PENDING_PAYMENT.value, BookingStatus.CONFIRMED.value}
_CANCELLATION_SCOPES = {scope.value for scope in RecurringCancellationScope}


class RecurringBookingService:
    """Preview, create, read, and cancel Recurring Booking Series."""

    def __init__(
        self,
        series_repository: RecurringBookingRepository,
        booking_repository: BookingRepository,
        pricing_service: PricingService,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
        user_read_service: UserReadService,
        override_log_repository: OverrideLogRepository,
        override_notifier: Optional[RecurringOverrideNotifierPort] = None,
        expiry_notifier: Optional[RecurringExpiryNotifierPort] = None,
        now_utc: Optional[Callable[[], datetime]] = None,
    ):
        self._series_repository = series_repository
        self._booking_repository = booking_repository
        self._pricing_service = pricing_service
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._user_read_service = user_read_service
        self._override_log_repository = override_log_repository
        self._override_notifier = override_notifier or NullRecurringOverrideNotifier()
        self._expiry_notifier = expiry_notifier or NullRecurringExpiryNotifier()
        self._now_utc = now_utc or (lambda: datetime.now(timezone.utc))
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
    async def preview_conflicts(self, command: CreateRecurringBookingSeriesCommand) -> RecurringBookingPreviewResult:
        prepared = await self._prepare_series(command)
        conflicts = await self._collect_conflicts(command, prepared)
        return RecurringBookingPreviewResult(conflicts=conflicts)

    @distributed_trace()
    async def create_series(self, command: CreateRecurringBookingSeriesCommand) -> RecurringBookingSeriesResult:
        prepared = await self._prepare_series(command)
        remaining, overridable_conflicts = await self._unexcluded_occurrences(command, prepared)
        booker_id = prepared.booker_id
        now_utc = prepared.now_utc
        is_priority = prepared.is_priority
        occurrence_dates = [item.occurrence_date for item in remaining]
        intervals = [(item.start_at, item.end_at) for item in remaining]

        occurrence_quotes = []
        series_quoted = Decimal("0")
        series_subtotal = Decimal("0")
        series_discount = Decimal("0")
        series_surcharge = Decimal("0")
        series_billed = Decimal("0")
        currency = "CAD"
        discount_percent = Decimal("0")
        for occurrence_date, (start_at, end_at) in zip(occurrence_dates, intervals, strict=True):
            billed_hours = self._billed_hours(start_at, end_at)
            quote_lines = [PreviewQuoteRoomLineCommand(facility_id=room.facility_id, billed_hours=billed_hours) for room in command.rooms]
            quote = await self._pricing_service.preview_quote(
                PreviewQuoteCommand(
                    booking_type=BookingType.RECURRING,
                    is_mission_aligned=command.is_mission_aligned,
                    currency="CAD",
                    as_of_date=occurrence_date,
                    room_lines=quote_lines,
                    surcharge_codes=command.surcharge_codes,
                    ministry_id=command.ministry_id,
                )
            )
            occurrence_quotes.append(quote)
            series_quoted += quote.quoted_amount
            series_subtotal += quote.subtotal_amount
            series_discount += quote.discount_amount
            series_surcharge += quote.surcharge_amount
            series_billed += sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
            currency = quote.currency
            discount_percent = quote.discount_percent

        hold_hours = await self._setting_service.get_pending_payment_hold_hours()
        payment_hold_expires_at = now_utc + timedelta(hours=hold_hours)
        series_id = uuid4()
        await self._series_repository.insert_series(
            dict(
                id=series_id,
                user_id=booker_id,
                ministry_id=command.ministry_id,
                first_occurrence_date=command.first_occurrence_date,
                last_occurrence_date=command.last_occurrence_date,
                local_start_time=command.local_start_time,
                local_end_time=command.local_end_time,
                status=BookingStatus.PENDING_PAYMENT.value,
                payment_hold_expires_at=payment_hold_expires_at,
                billed_hours=series_billed,
                subtotal_amount=series_subtotal,
                discount_percent=discount_percent,
                discount_amount=series_discount,
                surcharge_amount=series_surcharge,
                quoted_amount=series_quoted,
                currency=currency,
                is_mission_aligned=command.is_mission_aligned,
                is_priority=is_priority,
                remark=command.remark,
            )
        )

        occurrences: list[RecurringBookingOccurrenceResult] = []
        for (start_at, end_at), quote in zip(intervals, occurrence_quotes, strict=True):
            booking_id = uuid4()
            resolved_lines = [
                ResolvedBookingLine(facility_id=room.facility_id, start_at=start_at, end_at=end_at, sequence=room.sequence) for room in command.rooms
            ]
            primary_id = primary_facility_id(resolved_lines)
            total_billed = sum((line.billed_hours for line in quote.room_lines), Decimal("0"))
            await self._booking_repository.insert_booking(
                dict(
                    id=booking_id,
                    series_id=series_id,
                    user_id=booker_id,
                    facility_id=primary_id,
                    ministry_id=command.ministry_id,
                    booking_type=BookingType.RECURRING.value,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingStatus.PENDING_PAYMENT.value,
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
            await self._booking_repository.replace_booking_rooms(booking_id, room_rows)
            await self._booking_repository.replace_booking_slots(booking_id, slot_rows)
            occurrences.append(
                RecurringBookingOccurrenceResult(
                    id=booking_id,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingStatus.PENDING_PAYMENT.value,
                    quoted_amount=quote.quoted_amount,
                    currency=quote.currency,
                    facility_ids=[line.facility_id for line in resolved_lines],
                )
            )

        await self._apply_priority_overrides(
            command=command, prepared=prepared, series_id=series_id, occurrences=occurrences, remaining=remaining, overridable_conflicts=overridable_conflicts
        )

        return RecurringBookingSeriesResult(
            id=series_id,
            user_id=booker_id,
            ministry_id=command.ministry_id,
            first_occurrence_date=command.first_occurrence_date,
            last_occurrence_date=command.last_occurrence_date,
            local_start_time=command.local_start_time,
            local_end_time=command.local_end_time,
            status=BookingStatus.PENDING_PAYMENT.value,
            payment_hold_expires_at=payment_hold_expires_at,
            quoted_amount=series_quoted,
            currency=currency,
            occurrence_count=len(occurrences),
            is_priority=is_priority,
            occurrences=occurrences,
        )

    @distributed_trace()
    async def confirm_payment(self, series_id: UUID) -> RecurringBookingSeriesResult:
        operator_id = self._user_ctx.user_id if self._user_ctx else None
        if not operator_id:
            raise ForbiddenException(detail="Authenticated user required")
        series = await self._series_repository.get_by_id(series_id)
        if series is None:
            raise NotFoundException(detail="Recurring Booking Series not found", error_code=FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value)
        occurrences = await self._booking_repository.list_series_occurrences(series_id)
        if series.status == BookingStatus.CONFIRMED.value:
            return series.model_copy(update={"occurrences": occurrences, "occurrence_count": len(occurrences), "confirmed_by_id": series.confirmed_by_id})
        if series.status != BookingStatus.PENDING_PAYMENT.value or not is_pending_payment_hold_active(series.payment_hold_expires_at, self._now_utc()):
            raise BadRequestException(
                detail="Recurring Booking Series is not Pending-payment", error_code=FacilityErrorCode.BOOKING_SERIES_NOT_PENDING_PAYMENT.value
            )
        operator_name = self._user_ctx.username or self._user_ctx.email or "system"
        await self._series_repository.update_series(
            series_id, dict(status=BookingStatus.CONFIRMED.value, payment_hold_expires_at=None, updated_by_id=operator_id, updated_by=operator_name)
        )
        await self._booking_repository.confirm_pending_series_bookings(series_id, operator_id)
        confirmed_occurrences = await self._booking_repository.list_series_occurrences(series_id)
        return series.model_copy(
            update={
                "status": BookingStatus.CONFIRMED.value,
                "payment_hold_expires_at": None,
                "confirmed_by_id": operator_id,
                "occurrences": confirmed_occurrences,
                "occurrence_count": len(confirmed_occurrences),
            }
        )

    @distributed_trace()
    async def list_pending_payment_series(self) -> PendingPaymentSeriesListResult:
        items = await self._series_repository.list_pending_payment_series(self._now_utc(), self._resolved_locale_id())
        return PendingPaymentSeriesListResult(items=items)

    @distributed_trace()
    async def get_series(self, series_id: UUID) -> RecurringBookingSeriesResult:
        self._require_operator_id()
        return await self._series_with_occurrences(series_id)

    @distributed_trace()
    async def get_my_series(self, series_id: UUID) -> RecurringBookingSeriesResult:
        series = await self.get_series(series_id)
        self._raise_if_not_owner(series)
        return series

    @distributed_trace()
    async def cancel_series(self, series_id: UUID, command: CancelRecurringBookingSeriesCommand) -> RecurringBookingSeriesResult:
        self._require_operator_id()
        series = await self._series_with_occurrences(series_id)
        return await self._apply_cancellation(series, command)

    @distributed_trace()
    async def cancel_my_series(self, series_id: UUID, command: CancelRecurringBookingSeriesCommand) -> RecurringBookingSeriesResult:
        series = await self.get_my_series(series_id)
        return await self._apply_cancellation(series, command)

    @distributed_trace()
    async def preview_blackout_impact(self, blackout: RoomBlackoutResult) -> BlackoutImpactResult:
        if not blackout.is_active:
            return BlackoutImpactResult(confirmation_required=False, items=[])
        now = self._now_utc()
        local_tz = await self._setting_service.get_facility_timezone()
        candidates = await self._booking_repository.list_live_future_series_occurrences(now)
        items: list[BlackoutImpactOccurrenceResult] = []
        for occurrence in candidates:
            if any(
                self._blackout_repository.interval_overlaps_blackout(blackout, facility_id, occurrence.start_at, occurrence.end_at, local_tz)
                for facility_id in occurrence.facility_ids
            ):
                items.append(occurrence)
        return BlackoutImpactResult(confirmation_required=bool(items), items=items)

    @distributed_trace()
    async def apply_blackout_impact(self, items: list[BlackoutImpactOccurrenceResult], reason: str) -> BlackoutImpactResult:
        operator_id = self._require_operator_id()
        series_ids = {item.series_id for item in items}
        for occurrence in items:
            await self._booking_repository.cancel_booking(occurrence.id, operator_id, reason, True)
        now = self._now_utc()
        for series_id in series_ids:
            series = await self._series_with_occurrences(series_id)
            remaining_live = [item for item in series.occurrences if self._is_cancellable(item, now)]
            if not remaining_live and series.status != BookingStatus.CANCELLED.value:
                await self._series_repository.update_series(
                    series.id,
                    dict(status=BookingStatus.CANCELLED.value, payment_hold_expires_at=None, updated_by_id=operator_id, updated_by=self._operator_name()),
                )
        return BlackoutImpactResult(confirmation_required=False, items=items)

    @distributed_trace()
    async def expire_pending_holds(self) -> PendingPaymentExpirySweepResult:
        acquired = await self._series_repository.try_acquire_sweep_lock()
        if not acquired:
            return PendingPaymentExpirySweepResult(skipped=True)
        expired_series_ids: list[UUID] = []
        now_utc = self._now_utc()
        expired_series = await self._series_repository.list_expired_pending_series(now_utc)
        for series in expired_series:
            occurrences = await self._booking_repository.list_series_occurrences(series.id)
            pending_occurrences = [item for item in occurrences if item.status == BookingStatus.PENDING_PAYMENT.value]
            await self._series_repository.update_series(series.id, dict(status=BookingStatus.CANCELLED.value))
            for occurrence in pending_occurrences:
                await self._booking_repository.cancel_booking(occurrence.id, None, PENDING_PAYMENT_HOLD_EXPIRED_REASON, True)
            expired_series_ids.append(series.id)
            notification = RecurringPaymentHoldExpiryNotification(
                series_id=series.id, booker_id=series.user_id, quoted_amount=series.quoted_amount, currency=series.currency, occurrences=pending_occurrences
            )
            try:
                await self._expiry_notifier.notify_payment_hold_expired(notification)
            except Exception:
                logger.exception("Pending-payment hold expiry email failed for series %s", series.id)
        return PendingPaymentExpirySweepResult(skipped=False, expired_series_ids=expired_series_ids)

    @distributed_trace()
    async def release_pending_payment_sweep_lock(self) -> None:
        await self._series_repository.release_sweep_lock()

    def _require_operator_id(self) -> UUID:
        operator_id = self._user_ctx.user_id if self._user_ctx else None
        if not operator_id:
            raise ForbiddenException(detail="Authenticated user required")
        return operator_id

    def _operator_name(self) -> str:
        if not self._user_ctx:
            return "system"
        return self._user_ctx.username or self._user_ctx.email or "system"

    def _raise_if_not_owner(self, series: RecurringBookingSeriesResult) -> None:
        operator_id = self._require_operator_id()
        if series.user_id != operator_id:
            raise ForbiddenException(detail="Cannot access another user's Recurring Booking Series")

    async def _series_with_occurrences(self, series_id: UUID) -> RecurringBookingSeriesResult:
        series = await self._series_repository.get_by_id(series_id)
        if series is None:
            raise NotFoundException(detail="Recurring Booking Series not found", error_code=FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value)
        occurrences = await self._booking_repository.list_series_occurrences(series_id)
        return series.model_copy(update={"occurrences": occurrences, "occurrence_count": len(occurrences)})

    @staticmethod
    def _is_cancellable(occurrence: RecurringBookingOccurrenceResult, now: datetime) -> bool:
        return occurrence.status in _LIVE_OCCURRENCE_STATUSES and occurrence.start_at > now

    def _require_occurrence(self, occurrences: list[RecurringBookingOccurrenceResult], occurrence_id: Optional[UUID]) -> RecurringBookingOccurrenceResult:
        if occurrence_id is None:
            raise BadRequestException(
                detail="occurrence_id is required for this cancellation scope", error_code=FacilityErrorCode.RECURRING_OCCURRENCE_REQUIRED.value
            )
        match = next((item for item in occurrences if item.id == occurrence_id), None)
        if match is None:
            raise NotFoundException(detail="Booking Occurrence not found", error_code=FacilityErrorCode.RECURRING_OCCURRENCE_NOT_FOUND.value)
        return match

    def _cancellation_targets(
        self, occurrences: list[RecurringBookingOccurrenceResult], command: CancelRecurringBookingSeriesCommand, now: datetime
    ) -> list[RecurringBookingOccurrenceResult]:
        if command.scope == RecurringCancellationScope.OCCURRENCE.value:
            occurrence = self._require_occurrence(occurrences, command.occurrence_id)
            if occurrence.start_at <= now:
                raise BadRequestException(
                    detail="Historical Booking Occurrences cannot be cancelled", error_code=FacilityErrorCode.RECURRING_HISTORICAL_OCCURRENCE.value
                )
            return [occurrence] if self._is_cancellable(occurrence, now) else []
        if command.scope == RecurringCancellationScope.THIS_AND_FUTURE.value:
            pivot = self._require_occurrence(occurrences, command.occurrence_id)
            return [item for item in occurrences if item.start_at >= pivot.start_at and self._is_cancellable(item, now)]
        return [item for item in occurrences if self._is_cancellable(item, now)]

    async def _apply_cancellation(self, series: RecurringBookingSeriesResult, command: CancelRecurringBookingSeriesCommand) -> RecurringBookingSeriesResult:
        if command.scope not in _CANCELLATION_SCOPES:
            raise BadRequestException(
                detail="Cancellation scope must be occurrence, this_and_future, or entire_series",
                error_code=FacilityErrorCode.RECURRING_INVALID_CANCELLATION_SCOPE.value,
            )
        now = self._now_utc()
        targets = self._cancellation_targets(series.occurrences, command, now)
        operator_id = self._require_operator_id()
        for occurrence in targets:
            await self._booking_repository.cancel_booking(occurrence.id, operator_id, command.cancel_reason, True)
        refreshed = await self._booking_repository.list_series_occurrences(series.id)
        remaining_live = [item for item in refreshed if self._is_cancellable(item, now)]
        cancel_series = command.scope == RecurringCancellationScope.ENTIRE_SERIES.value or not remaining_live
        if cancel_series and series.status != BookingStatus.CANCELLED.value:
            await self._series_repository.update_series(
                series.id, dict(status=BookingStatus.CANCELLED.value, payment_hold_expires_at=None, updated_by_id=operator_id, updated_by=self._operator_name())
            )
        return await self._series_with_occurrences(series.id)

    async def _prepare_series(self, command: CreateRecurringBookingSeriesCommand) -> _PreparedSeries:
        operator_id = self._user_ctx.user_id if self._user_ctx else None
        if not operator_id:
            raise ForbiddenException(detail="Authenticated user required")
        booker_id = command.user_id or operator_id

        await self._raise_if_ineligible_booker(booker_id)
        if not command.rooms:
            raise BadRequestException(detail="At least one room is required", error_code=FacilityErrorCode.BOOKING_ROOMS_REQUIRED.value)
        if command.local_end_time <= command.local_start_time:
            raise BadRequestException(detail="local_end_time must be after local_start_time", error_code=FacilityErrorCode.RECURRING_INVALID_TIME_RANGE.value)

        max_lines = await self._setting_service.get_max_booking_lines()
        if len(command.rooms) > max_lines:
            raise BadRequestException(detail=f"At most {max_lines} rooms per booking", error_code=FacilityErrorCode.BOOKING_MAX_ROOMS.value)

        if command.last_occurrence_date < command.first_occurrence_date:
            raise BadRequestException(
                detail="last_occurrence_date must be on or after first_occurrence_date", error_code=FacilityErrorCode.RECURRING_INVALID_TIME_RANGE.value
            )
        if command.first_occurrence_date.weekday() != command.last_occurrence_date.weekday():
            raise BadRequestException(
                detail="first and last occurrence dates must fall on the same weekday", error_code=FacilityErrorCode.RECURRING_WEEKDAY_MISMATCH.value
            )

        first_period = use_period_for_date(command.first_occurrence_date)
        last_period = use_period_for_date(command.last_occurrence_date)
        if first_period != last_period:
            raise BadRequestException(
                detail="Recurring Booking Series must stay within one Recurring Booking period", error_code=FacilityErrorCode.RECURRING_USE_PERIOD.value
            )

        local_tz = await self._setting_service.get_facility_timezone()
        now_utc = self._now_utc()
        now_local = now_utc.astimezone(local_tz)
        window = await self._setting_service.get_recurring_booking_availability_window()
        opening = opening_date_for_period(first_period, command.first_occurrence_date.year)
        if not is_within_availability_window(now_local, opening, window.amount, window.unit):
            raise BadRequestException(
                detail="Recurring Booking period is outside the availability window", error_code=FacilityErrorCode.RECURRING_AVAILABILITY_WINDOW.value
            )

        occurrence_dates = weekly_occurrence_dates(command.first_occurrence_date, command.last_occurrence_date)
        min_weeks = await self._setting_service.get_min_recurring_booking_weeks()
        if len(occurrence_dates) < min_weeks:
            raise BadRequestException(
                detail=f"Recurring Booking Series requires at least {min_weeks} weekly occurrences",
                error_code=FacilityErrorCode.RECURRING_MIN_OCCURRENCES.value,
            )

        occurrences: list[_PreparedOccurrence] = []
        for occurrence_date in occurrence_dates:
            try:
                start_at = localize_wall_time(occurrence_date, command.local_start_time, local_tz).astimezone(timezone.utc)
                end_at = localize_wall_time(occurrence_date, command.local_end_time, local_tz).astimezone(timezone.utc)
            except ValueError as error:
                raise BadRequestException(
                    detail="Recurring Booking local time does not exist on a DST transition", error_code=FacilityErrorCode.RECURRING_DST_NONEXISTENT.value
                ) from error
            occurrences.append(_PreparedOccurrence(occurrence_date=occurrence_date, start_at=start_at, end_at=end_at))

        first = occurrences[0]
        validate_booking_lines(
            [ResolvedBookingLine(facility_id=room.facility_id, start_at=first.start_at, end_at=first.end_at, sequence=room.sequence) for room in command.rooms],
            local_tz,
        )

        is_priority = False
        ministry_name = None
        ministry_name_zh = None
        if command.ministry_id is not None:
            is_priority, ministry_name, ministry_name_zh = await self._validate_ministry_series(command.ministry_id, booker_id)
        return _PreparedSeries(
            booker_id=booker_id,
            operator_id=operator_id,
            local_tz=local_tz,
            now_utc=now_utc,
            occurrences=occurrences,
            is_priority=is_priority,
            ministry_name=ministry_name,
            ministry_name_zh=ministry_name_zh,
        )

    async def _unexcluded_occurrences(
        self, command: CreateRecurringBookingSeriesCommand, prepared: _PreparedSeries
    ) -> tuple[list[_PreparedOccurrence], list[RecurringBookingConflictResult]]:
        conflicts = await self._collect_conflicts(command, prepared)
        generated_dates = {item.occurrence_date for item in prepared.occurrences}
        conflict_dates = {item.occurrence_date for item in conflicts}
        excluded_dates = set(command.excluded_dates)
        if excluded_dates - generated_dates or excluded_dates - conflict_dates:
            raise BadRequestException(
                detail="excluded_dates must be occurrence dates that currently conflict", error_code=FacilityErrorCode.RECURRING_INVALID_EXCLUSION.value
            )
        remaining = [item for item in prepared.occurrences if item.occurrence_date not in excluded_dates]
        min_weeks = await self._setting_service.get_min_recurring_booking_weeks()
        if len(remaining) < min_weeks:
            raise BadRequestException(
                detail=f"Recurring Booking Series requires at least {min_weeks} weekly occurrences",
                error_code=FacilityErrorCode.RECURRING_MIN_OCCURRENCES.value,
            )
        remaining_conflicts = [item for item in conflicts if item.occurrence_date not in excluded_dates]
        blocking = [item for item in remaining_conflicts if not item.is_overridable]
        if blocking:
            self._raise_remaining_conflict(blocking[0])
        overridable = [item for item in remaining_conflicts if item.is_overridable]
        return remaining, overridable

    @staticmethod
    def _raise_remaining_conflict(conflict: RecurringBookingConflictResult) -> None:
        facility_id = conflict.facility_ids[0] if conflict.facility_ids else None
        if conflict.kind == RecurringConflictKind.MINISTRY.value:
            raise ConflictErrorException(
                detail="Room is occupied by another Ministry Series",
                error_code=FacilityErrorCode.RECURRING_MINISTRY_CONFLICT.value,
                context={
                    "facility_id": str(facility_id) if facility_id else None,
                    "ministry_id": str(conflict.ministry_id) if conflict.ministry_id else None,
                    "ministry_steward_display_name": conflict.ministry_steward_display_name,
                    "ministry_steward_email": conflict.ministry_steward_email,
                },
            )
        if conflict.kind == RecurringConflictKind.OCCUPANCY.value:
            raise ConflictErrorException(
                detail=f"Room {facility_id} has a scheduling conflict",
                error_code=BookingErrorCode.SCHEDULING_CONFLICT.value,
                context={"facility_id": str(facility_id)} if facility_id else None,
            )
        if conflict.kind == RecurringConflictKind.BLACKOUT.value:
            raise BadRequestException(
                detail=f"Room {facility_id} is closed for the selected time",
                error_code=BookingErrorCode.ROOM_BLACKOUT.value,
                context={"facility_id": str(facility_id)} if facility_id else None,
            )
        raise BadRequestException(
            detail="Booker already has a Rental Booking in that facility-local week", error_code=FacilityErrorCode.RECURRING_WEEKLY_QUOTA.value
        )

    async def _collect_conflicts(self, command: CreateRecurringBookingSeriesCommand, prepared: _PreparedSeries) -> list[RecurringBookingConflictResult]:
        conflicts: list[RecurringBookingConflictResult] = []
        if command.ministry_id is None:
            quota_dates = await self._weekly_quota_conflict_dates(prepared.booker_id, prepared.occurrences, prepared.local_tz)
            for occurrence_date in quota_dates:
                conflicts.append(
                    RecurringBookingConflictResult(occurrence_date=occurrence_date, kind=RecurringConflictKind.WEEKLY_QUOTA.value, facility_ids=[])
                )
        for occurrence in prepared.occurrences:
            occupying = await self._occupying_bookings_for_occurrence(command, occurrence)
            rental_overridable: list[RecurringOccupyingBookingResult] = []
            rental_blocked: list[RecurringOccupyingBookingResult] = []
            ministry_items: list[RecurringOccupyingBookingResult] = []
            for item in occupying:
                if item.ministry_id:
                    ministry_items.append(item)
                elif prepared.is_priority and item.start_at > prepared.now_utc:
                    rental_overridable.append(item)
                else:
                    rental_blocked.append(item)
            if rental_overridable:
                conflicts.append(
                    RecurringBookingConflictResult(
                        occurrence_date=occurrence.occurrence_date,
                        kind=RecurringConflictKind.OCCUPANCY.value,
                        facility_ids=self._unique_facility_ids(rental_overridable),
                        is_overridable=True,
                        occupying_bookings=rental_overridable,
                    )
                )
            if rental_blocked:
                conflicts.append(
                    RecurringBookingConflictResult(
                        occurrence_date=occurrence.occurrence_date,
                        kind=RecurringConflictKind.OCCUPANCY.value,
                        facility_ids=self._unique_facility_ids(rental_blocked),
                        occupying_bookings=rental_blocked,
                    )
                )
            if ministry_items:
                first = ministry_items[0]
                steward_name, steward_email = await self._primary_steward_contact(first.ministry_id)
                conflicts.append(
                    RecurringBookingConflictResult(
                        occurrence_date=occurrence.occurrence_date,
                        kind=RecurringConflictKind.MINISTRY.value,
                        facility_ids=self._unique_facility_ids(ministry_items),
                        occupying_bookings=ministry_items,
                        ministry_id=first.ministry_id,
                        ministry_steward_display_name=steward_name,
                        ministry_steward_email=steward_email,
                    )
                )
            blackout_ids: list[UUID] = []
            for room in command.rooms:
                if await self._blackout_repository.has_blackout_overlap(
                    facility_id=room.facility_id, start_at=occurrence.start_at, end_at=occurrence.end_at, tz=prepared.local_tz
                ):
                    blackout_ids.append(room.facility_id)
            if blackout_ids:
                conflicts.append(
                    RecurringBookingConflictResult(
                        occurrence_date=occurrence.occurrence_date, kind=RecurringConflictKind.BLACKOUT.value, facility_ids=blackout_ids
                    )
                )
        kind_order = {
            RecurringConflictKind.OCCUPANCY.value: 0,
            RecurringConflictKind.MINISTRY.value: 1,
            RecurringConflictKind.BLACKOUT.value: 2,
            RecurringConflictKind.WEEKLY_QUOTA.value: 3,
        }
        conflicts.sort(key=lambda item: (item.occurrence_date, kind_order[item.kind], 0 if item.is_overridable else 1))
        return conflicts

    async def _occupying_bookings_for_occurrence(
        self, command: CreateRecurringBookingSeriesCommand, occurrence: _PreparedOccurrence
    ) -> list[RecurringOccupyingBookingResult]:
        merged: dict[UUID, RecurringOccupyingBookingResult] = {}
        for room in command.rooms:
            rows = await self._booking_repository.list_occupying_slots(facility_id=room.facility_id, start_at=occurrence.start_at, end_at=occurrence.end_at)
            for item in rows:
                facility_ids = list(dict.fromkeys([*item.facility_ids, room.facility_id]))
                existing = merged.get(item.booking_id)
                if existing:
                    merged[item.booking_id] = existing.model_copy(update={"facility_ids": list(dict.fromkeys([*existing.facility_ids, *facility_ids]))})
                else:
                    merged[item.booking_id] = item.model_copy(update={"facility_ids": facility_ids})
        return list(merged.values())

    @staticmethod
    def _unique_facility_ids(items: list[RecurringOccupyingBookingResult]) -> list[UUID]:
        facility_ids: list[UUID] = []
        for item in items:
            for facility_id in item.facility_ids:
                if facility_id not in facility_ids:
                    facility_ids.append(facility_id)
        return facility_ids

    async def _weekly_quota_conflict_dates(self, booker_id: UUID, occurrences: list[_PreparedOccurrence], local_tz: ZoneInfo) -> list[date]:
        local_dates = [item.start_at.astimezone(local_tz).date() for item in occurrences]
        first_week = sunday_week_start(min(local_dates))
        last_week = sunday_week_start(max(local_dates))
        range_start = datetime.combine(first_week, time.min, tzinfo=local_tz).astimezone(timezone.utc)
        range_end = datetime.combine(last_week + timedelta(days=7), time.min, tzinfo=local_tz).astimezone(timezone.utc)
        existing = await self._booking_repository.list_rental_occurrence_starts(booker_id, range_start, range_end)
        occupied_weeks = {sunday_week_start(start_at.astimezone(local_tz).date()) for start_at in existing}
        return [item.occurrence_date for item in occurrences if sunday_week_start(item.start_at.astimezone(local_tz).date()) in occupied_weeks]

    async def _raise_if_ineligible_booker(self, booker_id: UUID) -> None:
        email = None
        if self._user_ctx and self._user_ctx.user_id == booker_id:
            email = self._user_ctx.email
        if not email:
            user = await self._user_read_service.get_user_sensitive_by_id(booker_id)
            email = user.email if user else None
        if not is_church_email(email, CHURCH_EMAIL_DOMAIN):
            raise ForbiddenException(detail="Facility Booking requires a church-domain account", error_code=FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value)

    async def _validate_ministry_series(self, ministry_id: UUID, booker_id: UUID) -> tuple[bool, Optional[str]]:
        ministry = await self._ministry_repository.get_by_id(ministry_id, all_locales=True)
        status = ministry.status if ministry else await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(
                detail="Ministry must be active for booking",
                error_code=FacilityErrorCode.BOOKING_MINISTRY_INACTIVE.value,
                context={"ministry_id": str(ministry_id)},
            )
        if not await self._ministry_repository.is_user_booking_member(ministry_id, booker_id):
            raise ForbiddenException(detail="User is not a ministry owner")
        is_priority = bool(ministry.has_priority_booking) if ministry else False
        name_en, name_zh = resolve_bilingual_activity_names(ministry.translations if ministry else [], ministry.name if ministry else None)
        return is_priority, name_en, name_zh

    async def _primary_steward_contact(self, ministry_id: Optional[UUID]) -> tuple[Optional[str], Optional[str]]:
        if ministry_id is None:
            return None, None
        members = await self._ministry_repository.list_members(ministry_id)
        primary = next((member for member in members if member.member_role == MinistryMemberRole.PRIMARY.value), None)
        if primary is None:
            return None, None
        display_name = primary.display_name or primary.email
        return display_name, primary.email

    async def _apply_priority_overrides(
        self,
        *,
        command: CreateRecurringBookingSeriesCommand,
        prepared: _PreparedSeries,
        series_id: UUID,
        occurrences: list[RecurringBookingOccurrenceResult],
        remaining: list[_PreparedOccurrence],
        overridable_conflicts: list[RecurringBookingConflictResult],
    ) -> None:
        if not overridable_conflicts:
            return
        occurrence_id_by_date = {item.occurrence_date: occurrence.id for item, occurrence in zip(remaining, occurrences, strict=True)}
        log_rows: list[dict] = []
        notification_items: list[RecurringOverrideNotificationItem] = []
        overridden_ids: set[UUID] = set()
        for conflict in overridable_conflicts:
            church_activity_booking_id = occurrence_id_by_date[conflict.occurrence_date]
            for occupying in conflict.occupying_bookings:
                if occupying.booking_id not in overridden_ids:
                    await self._booking_repository.override_booking(occupying.booking_id, prepared.operator_id, "Priority Ministry override")
                    overridden_ids.add(occupying.booking_id)
                for facility_id in occupying.facility_ids:
                    log_rows.append(
                        dict(
                            id=uuid4(),
                            facility_booking_id=church_activity_booking_id,
                            overridden_booking_id=occupying.booking_id,
                            overridden_by_id=prepared.operator_id,
                            facility_id=facility_id,
                            outcome=OverrideOutcome.OVERRIDE_APPLIED.value,
                            reason="Priority Ministry override",
                        )
                    )
                notification_items.append(
                    RecurringOverrideNotificationItem(
                        booking_id=occupying.booking_id,
                        booker_id=occupying.user_id,
                        occurrence_date=conflict.occurrence_date,
                        facility_ids=occupying.facility_ids,
                        church_activity_booking_id=church_activity_booking_id,
                    )
                )
        if log_rows:
            await self._override_log_repository.insert_logs(log_rows)
        if not notification_items or command.ministry_id is None:
            return
        notification = RecurringOverrideNotification(
            series_id=series_id,
            ministry_id=command.ministry_id,
            church_activity_name=prepared.ministry_name or "Church Activity",
            church_activity_name_zh=prepared.ministry_name_zh or prepared.ministry_name or "Church Activity",
            actor_id=prepared.operator_id,
            items=notification_items,
        )
        try:
            await self._override_notifier.notify_priority_override(notification)
        except Exception:
            logger.exception("Priority Ministry override email failed for series %s", series_id)
