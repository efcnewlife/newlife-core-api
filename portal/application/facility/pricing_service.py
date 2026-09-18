"""
Facility rental pricing service.
"""

from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from uuid import UUID

from portal.application.facility.commands import EvaluateDiscountEligibilityCommand, PreviewQuoteCommand
from portal.application.facility.discount_eligibility_service import DiscountEligibilityService
from portal.application.facility.results import PreviewQuoteResult, PreviewQuoteRoomLineResult, RentalRateResult
from portal.domain.facility.constants import RentalRateBillingUnit, RentalSurchargeChargeType
from portal.exceptions.responses import BadRequestException
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from portal.infrastructure.persistence.repositories.facility.room_repository import RoomRepository
from portal.libs.tracing.distributed_trace import distributed_trace

MONEY_QUANT = Decimal("0.01")


class PricingService:
    """Rental quote calculation per booking room lines."""

    def __init__(self, rental_repository: RentalRepository, room_repository: RoomRepository, discount_eligibility_service: DiscountEligibilityService):
        self._rental_repository = rental_repository
        self._room_repository = room_repository
        self._discount_eligibility_service = discount_eligibility_service

    @staticmethod
    def _quantize(amount: Decimal) -> Decimal:
        return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)

    async def _resolve_rate_for_room(self, facility_id: UUID, billed_hours: Decimal, as_of_date) -> Optional[RentalRateResult]:
        room_rates = await self._rental_repository.list_active_rates_for_facility(facility_id=facility_id, as_of_date=as_of_date)
        if room_rates:
            rate, _tier = self._rental_repository.pick_rate_for_line(rates=room_rates, billed_hours=billed_hours, allow_first_active=False)
            if rate:
                return rate

        templates = await self._rental_repository.list_templates(active_only=True)
        candidates = [self._rental_repository.template_to_rate_candidate(template) for template in templates]
        rate, _tier = self._rental_repository.pick_rate_for_line(rates=candidates, billed_hours=billed_hours, allow_first_active=True)
        return rate

    @distributed_trace()
    async def preview_quote(self, command: PreviewQuoteCommand) -> PreviewQuoteResult:
        """
        Compute preview quote for room lines, discounts, and surcharges.
        """
        if not command.room_lines:
            raise BadRequestException(detail="At least one room line is required")

        room_lines: list[PreviewQuoteRoomLineResult] = []
        subtotal = Decimal("0")

        for line in command.room_lines:
            if not await self._room_repository.exists_by_id(line.facility_id):
                raise BadRequestException(detail=f"Room {line.facility_id} not found")
            if line.billed_hours <= 0:
                raise BadRequestException(detail="billed_hours must be positive")

            rate = await self._resolve_rate_for_room(facility_id=line.facility_id, billed_hours=line.billed_hours, as_of_date=command.as_of_date)
            if not rate:
                raise BadRequestException(detail=f"No active rental rate for room {line.facility_id}")

            billing_unit = rate.billing_unit or RentalRateBillingUnit.HOURLY.value
            line_subtotal = self._compute_line_subtotal(billing_unit, rate.unit_amount, line.billed_hours)
            subtotal += line_subtotal
            room_lines.append(
                PreviewQuoteRoomLineResult(
                    facility_id=line.facility_id,
                    billed_hours=line.billed_hours,
                    rental_rate_name=rate.template_name or "",
                    billing_unit=billing_unit,
                    unit_amount=rate.unit_amount,
                    currency=rate.currency or "CAD",
                    applicability=rate.applicability,
                    is_default=rate.is_default,
                    line_subtotal=self._quantize(line_subtotal),
                )
            )

        eligibility = await self._discount_eligibility_service.evaluate(
            EvaluateDiscountEligibilityCommand(booking_type=command.booking_type, ministry_id=command.ministry_id, booker_id=command.booker_id)
        )
        discount_percent = eligibility.discount_percent
        discount_amount = self._quantize(subtotal * discount_percent / Decimal("100"))
        after_discount = subtotal - discount_amount
        surcharge_amount = await self._compute_surcharges(command, after_discount)
        quoted_amount = after_discount + surcharge_amount

        return PreviewQuoteResult(
            subtotal_amount=self._quantize(subtotal),
            discount_code=eligibility.discount_code,
            discount_percent=discount_percent,
            discount_amount=discount_amount,
            surcharge_amount=self._quantize(surcharge_amount),
            quoted_amount=self._quantize(quoted_amount),
            currency=command.currency,
            room_lines=room_lines,
        )

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
