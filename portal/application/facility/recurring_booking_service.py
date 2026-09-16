"""
Recurring Booking Series application service.
"""

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Callable, Optional
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from portal.application.auth.user_read_service import UserReadService
from portal.application.facility.booking_line_validation import ResolvedBookingLine, primary_facility_id, validate_booking_lines
from portal.application.facility.commands import CreateRecurringBookingSeriesCommand, PreviewQuoteCommand, PreviewQuoteRoomLineCommand
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.results import RecurringBookingOccurrenceResult, RecurringBookingSeriesResult
from portal.application.system.setting_service import SettingService
from portal.domain.facility.constants import CHURCH_EMAIL_DOMAIN, BookingErrorCode, BookingSlotStatus, BookingStatus, BookingType, FacilityErrorCode
from portal.domain.facility.recurring import (
    is_church_email,
    is_within_availability_window,
    localize_wall_time,
    opening_date_for_period,
    sunday_week_start,
    use_period_for_date,
    weekly_occurrence_dates,
)
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.recurring_booking_repository import RecurringBookingRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.libs.contexts.user_context import UserContext, get_user_context
from portal.libs.tracing.distributed_trace import distributed_trace


class RecurringBookingService:
    """Create Recurring Booking Series and materialize weekly Booking Occurrences."""

    def __init__(
        self,
        series_repository: RecurringBookingRepository,
        booking_repository: BookingRepository,
        pricing_service: PricingService,
        ministry_repository: MinistryRepository,
        room_blackout_repository: RoomBlackoutRepository,
        setting_service: SettingService,
        user_read_service: UserReadService,
        now_utc: Optional[Callable[[], datetime]] = None,
    ):
        self._series_repository = series_repository
        self._booking_repository = booking_repository
        self._pricing_service = pricing_service
        self._ministry_repository = ministry_repository
        self._blackout_repository = room_blackout_repository
        self._setting_service = setting_service
        self._user_read_service = user_read_service
        self._now_utc = now_utc or (lambda: datetime.now(timezone.utc))
        self._user_ctx: Optional[UserContext] = get_user_context()

    @staticmethod
    def _billed_hours(start_at: datetime, end_at: datetime) -> Decimal:
        delta = end_at - start_at
        hours = Decimal(str(delta.total_seconds())) / Decimal("3600")
        return hours.quantize(Decimal("0.01"))

    @distributed_trace()
    async def create_series(self, command: CreateRecurringBookingSeriesCommand) -> RecurringBookingSeriesResult:
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

        intervals: list[tuple[datetime, datetime]] = []
        for occurrence_date in occurrence_dates:
            try:
                start_at = localize_wall_time(occurrence_date, command.local_start_time, local_tz).astimezone(timezone.utc)
                end_at = localize_wall_time(occurrence_date, command.local_end_time, local_tz).astimezone(timezone.utc)
            except ValueError as error:
                raise BadRequestException(
                    detail="Recurring Booking local time does not exist on a DST transition", error_code=FacilityErrorCode.RECURRING_DST_NONEXISTENT.value
                ) from error
            intervals.append((start_at, end_at))

        first_start, first_end = intervals[0]
        validate_booking_lines(
            [ResolvedBookingLine(facility_id=room.facility_id, start_at=first_start, end_at=first_end, sequence=room.sequence) for room in command.rooms],
            local_tz,
        )

        is_priority = False
        if command.ministry_id is not None:
            is_priority = await self._validate_ministry_series(command.ministry_id, booker_id)
        else:
            await self._raise_if_weekly_quota_conflict(booker_id, [start_at for start_at, _end_at in intervals], local_tz)

        for start_at, end_at in intervals:
            for room in command.rooms:
                await self._raise_if_room_unavailable(room.facility_id, start_at, end_at, local_tz)

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

    async def _raise_if_ineligible_booker(self, booker_id: UUID) -> None:
        email = None
        if self._user_ctx and self._user_ctx.user_id == booker_id:
            email = self._user_ctx.email
        if not email:
            user = await self._user_read_service.get_user_sensitive_by_id(booker_id)
            email = user.email if user else None
        if not is_church_email(email, CHURCH_EMAIL_DOMAIN):
            raise ForbiddenException(detail="Facility Booking requires a church-domain account", error_code=FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value)

    async def _validate_ministry_series(self, ministry_id: UUID, booker_id: UUID) -> bool:
        ministry = await self._ministry_repository.get_by_id(ministry_id)
        status = ministry.status if ministry else await self._ministry_repository.get_status(ministry_id)
        if status != MinistryStatus.ACTIVE.value:
            raise BadRequestException(
                detail="Ministry must be active for booking",
                error_code=FacilityErrorCode.BOOKING_MINISTRY_INACTIVE.value,
                context={"ministry_id": str(ministry_id)},
            )
        if not await self._ministry_repository.is_user_booking_member(ministry_id, booker_id):
            raise ForbiddenException(detail="User is not a ministry owner")
        return bool(ministry.has_priority_booking) if ministry else False

    async def _raise_if_weekly_quota_conflict(self, booker_id: UUID, occurrence_starts: list[datetime], local_tz: ZoneInfo) -> None:
        local_dates = [start_at.astimezone(local_tz).date() for start_at in occurrence_starts]
        first_week = sunday_week_start(min(local_dates))
        last_week = sunday_week_start(max(local_dates))
        range_start = datetime.combine(first_week, time.min, tzinfo=local_tz).astimezone(timezone.utc)
        range_end = datetime.combine(last_week + timedelta(days=7), time.min, tzinfo=local_tz).astimezone(timezone.utc)
        existing = await self._booking_repository.list_rental_occurrence_starts(booker_id, range_start, range_end)
        occupied_weeks = {sunday_week_start(start_at.astimezone(local_tz).date()) for start_at in existing}
        for start_at in occurrence_starts:
            week_start = sunday_week_start(start_at.astimezone(local_tz).date())
            if week_start in occupied_weeks:
                raise BadRequestException(
                    detail="Booker already has a Rental Booking in that facility-local week", error_code=FacilityErrorCode.RECURRING_WEEKLY_QUOTA.value
                )
            occupied_weeks.add(week_start)

    async def _raise_if_room_unavailable(self, facility_id: UUID, start_at: datetime, end_at: datetime, local_tz: ZoneInfo) -> None:
        if await self._booking_repository.has_confirmed_slot_overlap(facility_id=facility_id, start_at=start_at, end_at=end_at):
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
