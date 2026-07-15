"""
Facility rental pricing service.
"""
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import PreviewQuoteCommand
from portal.application.facility.results import PreviewQuoteResult, PreviewQuoteRoomLineResult
from portal.domain.facility.constants import (
    BookingType,
    RentalDiscountCode,
    RentalPolicySettingKey,
    RentalRateBillingUnit,
    RentalSurchargeChargeType,
)
from portal.exceptions.responses import BadRequestException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.tracing.distributed_trace import distributed_trace

DEFAULT_MINIMUM_FEE = Decimal("0")
MONEY_QUANT = Decimal("0.01")


class PricingService:
    """Rental quote calculation per booking room lines."""

    def __init__(
        self,
        rental_repository: RentalRepository,
        room_repository: RoomRepository,
    ):
        self._rental_repository = rental_repository
        self._room_repository = room_repository

    @staticmethod
    def _quantize(amount: Decimal) -> Decimal:
        return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    @distributed_trace()
    async def preview_quote(self, command: PreviewQuoteCommand) -> PreviewQuoteResult:
        """
        Compute preview quote for room lines, discounts, surcharges, and minimum fee.
        """
        if not command.room_lines:
            raise BadRequestException(detail="At least one room line is required")

        room_lines: list[PreviewQuoteRoomLineResult] = []
        subtotal = Decimal("0")
        primary_facility_id = command.room_lines[0].facility_id

        for line in command.room_lines:
            if not await self._room_repository.exists_by_id(line.facility_id):
                raise BadRequestException(detail=f"Room {line.facility_id} not found")
            if line.billed_hours <= 0:
                raise BadRequestException(detail="billed_hours must be positive")

            rates = await self._rental_repository.list_active_rates_for_facility(
                facility_id=line.facility_id,
                as_of_date=command.as_of_date,
            )
            rate, tier = self._rental_repository.pick_rate_for_line(
                rates=rates,
                billed_hours=line.billed_hours,
            )
            if not rate:
                raise BadRequestException(detail=f"No active rental rate for room {line.facility_id}")

            line_subtotal = self._compute_line_subtotal(rate.billing_unit, rate.unit_amount, line.billed_hours)
            subtotal += line_subtotal
            room_lines.append(
                PreviewQuoteRoomLineResult(
                    facility_id=line.facility_id,
                    billed_hours=line.billed_hours,
                    pricing_tier_used=tier,
                    rental_rate_id=rate.id,
                    line_subtotal=self._quantize(line_subtotal),
                )
            )

        discount_percent = Decimal("0")
        if command.is_mission_aligned:
            discount_percent = await self._mission_discount_percent(Decimal("0"))
        elif command.booking_type == BookingType.RECURRING:
            discount_percent = await self._recurring_discount_percent(Decimal("0"))

        discount_amount = self._quantize(subtotal * discount_percent / Decimal("100"))
        after_discount = subtotal - discount_amount
        surcharge_amount = await self._compute_surcharges(command, after_discount)
        quoted_before_floor = after_discount + surcharge_amount
        minimum_fee = await self._resolve_minimum_fee(primary_facility_id)
        quoted_amount = max(quoted_before_floor, minimum_fee)

        return PreviewQuoteResult(
            subtotal_amount=self._quantize(subtotal),
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            surcharge_amount=self._quantize(surcharge_amount),
            quoted_amount=self._quantize(quoted_amount),
            currency=command.currency,
            room_lines=room_lines,
        )

    async def _mission_discount_percent(self, fallback: Decimal) -> Decimal:
        rules = await self._rental_repository.list_discount_rules()
        for rule in rules:
            if rule.code == RentalDiscountCode.MISSION_ALIGNED.value and rule.is_active:
                return Decimal(str(rule.percent_off))
        return fallback

    async def _recurring_discount_percent(self, fallback: Decimal) -> Decimal:
        rules = await self._rental_repository.list_discount_rules()
        for rule in rules:
            if rule.code == RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value and rule.is_active:
                return Decimal(str(rule.percent_off))
        return fallback

    @staticmethod
    def _compute_line_subtotal(billing_unit: str, unit_amount: Decimal, billed_hours: Decimal) -> Decimal:
        amount = Decimal(str(unit_amount))
        if billing_unit == RentalRateBillingUnit.DAILY_FLAT.value:
            return amount
        if billing_unit == RentalRateBillingUnit.HOURLY.value:
            return amount * billed_hours
        if billing_unit == RentalRateBillingUnit.PER_SLOT.value:
            return amount
        if billing_unit == RentalRateBillingUnit.FLAT_PER_BOOKING.value:
            return amount
        return amount * billed_hours

    async def _resolve_minimum_fee(self, facility_id: UUID) -> Decimal:
        amount = await self._rental_repository.get_policy_amount(
            RentalPolicySettingKey.MINIMUM_FEE_GYM,
            facility_id,
        )
        if amount is None:
            amount = await self._rental_repository.get_policy_amount(
                RentalPolicySettingKey.MINIMUM_FEE_DEFAULT,
                facility_id,
            )
        if amount is None:
            return DEFAULT_MINIMUM_FEE
        return amount

    async def _compute_surcharges(self, command: PreviewQuoteCommand, base_amount: Decimal) -> Decimal:
        if not command.surcharge_codes:
            return Decimal("0")
        surcharges = await self._rental_repository.list_surcharges()
        active = {item.code: item for item in surcharges if item.is_active}
        total = Decimal("0")
        billed_hours = sum((line.billed_hours for line in command.room_lines), Decimal("0"))
        for code in command.surcharge_codes:
            surcharge = active.get(code)
            if not surcharge:
                raise BadRequestException(detail=f"Surcharge code {code} not found or inactive")
            unit_amount = Decimal(str(surcharge.unit_amount))
            if surcharge.charge_type == RentalSurchargeChargeType.PER_HOUR.value:
                total += unit_amount * billed_hours
            else:
                total += unit_amount
        return total
