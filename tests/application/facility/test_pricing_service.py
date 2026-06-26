"""
PricingService.preview_quote tests.
"""
from decimal import Decimal

import pytest

from portal.application.facility.commands import PreviewQuoteCommand, PreviewQuoteRoomLineCommand
from portal.application.facility.pricing_service import PricingService
from portal.domain.facility.constants import (
    BookingType,
    RentalDiscountCode,
    RentalPolicySettingKey,
    RentalRateBillingUnit,
    RentalSurchargeChargeType,
)
from portal.exceptions.responses import BadRequestException
from tests.fixtures.facility.factories import (
    make_discount_rule,
    make_hourly_and_daily_rates,
    make_preview_quote_command,
    make_rental_rate,
    make_surcharge,
    new_uuid,
)
from tests.fixtures.facility.stubs import StubRentalRepository, StubRoomRepository


def _pricing_service(rental_stub: StubRentalRepository, room_ids: set | None = None) -> PricingService:
    room_stub = StubRoomRepository(existing_ids=room_ids or set())
    return PricingService(rental_stub, room_stub)


@pytest.mark.asyncio
async def test_preview_quote_requires_room_lines():
    service = _pricing_service(StubRentalRepository())
    with pytest.raises(BadRequestException, match="At least one room line"):
        await service.preview_quote(PreviewQuoteCommand(booking_type=BookingType.ONE_TIME, room_lines=[]))


@pytest.mark.asyncio
async def test_preview_quote_room_not_found():
    room_id = new_uuid()
    service = _pricing_service(StubRentalRepository(), room_ids=set())
    command = make_preview_quote_command(facility_id=room_id)
    with pytest.raises(BadRequestException, match="not found"):
        await service.preview_quote(command)


@pytest.mark.asyncio
async def test_preview_quote_rejects_non_positive_billed_hours():
    room_id = new_uuid()
    service = _pricing_service(StubRentalRepository(), room_ids={room_id})
    command = PreviewQuoteCommand(
        booking_type=BookingType.ONE_TIME,
        room_lines=[PreviewQuoteRoomLineCommand(facility_id=room_id, billed_hours=Decimal("0"))],
    )
    with pytest.raises(BadRequestException, match="billed_hours"):
        await service.preview_quote(command)


@pytest.mark.asyncio
async def test_preview_quote_hourly_subtotal_below_threshold():
    room_id = new_uuid()
    rental = StubRentalRepository(rates_by_facility={room_id: make_hourly_and_daily_rates(room_id)})
    service = _pricing_service(rental, {room_id})
    result = await service.preview_quote(make_preview_quote_command(facility_id=room_id, billed_hours=Decimal("4")))
    assert result.subtotal_amount == Decimal("40.00")
    assert result.room_lines[0].pricing_tier_used == RentalRateBillingUnit.HOURLY.value


@pytest.mark.asyncio
async def test_preview_quote_daily_flat_subtotal_for_six_hours():
    room_id = new_uuid()
    rental = StubRentalRepository(rates_by_facility={room_id: make_hourly_and_daily_rates(room_id)})
    service = _pricing_service(rental, {room_id})
    result = await service.preview_quote(make_preview_quote_command(facility_id=room_id, billed_hours=Decimal("6")))
    assert result.room_lines[0].pricing_tier_used == RentalRateBillingUnit.DAILY_FLAT.value
    assert result.subtotal_amount == Decimal("200.00")


@pytest.mark.asyncio
async def test_preview_quote_sums_multiple_room_lines():
    room_a = new_uuid()
    room_b = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={
            room_a: make_hourly_and_daily_rates(room_a, hourly_amount=Decimal("10")),
            room_b: make_hourly_and_daily_rates(room_b, hourly_amount=Decimal("20")),
        }
    )
    service = _pricing_service(rental, {room_a, room_b})
    command = PreviewQuoteCommand(
        booking_type=BookingType.ONE_TIME,
        room_lines=[
            PreviewQuoteRoomLineCommand(facility_id=room_a, billed_hours=Decimal("2")),
            PreviewQuoteRoomLineCommand(facility_id=room_b, billed_hours=Decimal("2")),
        ],
    )
    result = await service.preview_quote(command)
    assert result.subtotal_amount == Decimal("60.00")


@pytest.mark.asyncio
async def test_preview_quote_mission_discount_not_stacked_with_recurring():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={room_id: make_hourly_and_daily_rates(room_id)},
        discount_rules=[
            make_discount_rule(RentalDiscountCode.MISSION_ALIGNED.value, Decimal("30")),
            make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20")),
        ],
    )
    service = _pricing_service(rental, {room_id})
    command = make_preview_quote_command(
        facility_id=room_id,
        billed_hours=Decimal("6"),
        booking_type=BookingType.RECURRING,
        is_mission_aligned=True,
    )
    result = await service.preview_quote(command)
    assert result.discount_percent == Decimal("30")
    assert result.discount_amount == Decimal("60.00")


@pytest.mark.asyncio
async def test_preview_quote_recurring_discount():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={room_id: make_hourly_and_daily_rates(room_id)},
        discount_rules=[make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20"))],
    )
    service = _pricing_service(rental, {room_id})
    command = make_preview_quote_command(
        facility_id=room_id,
        booking_type=BookingType.RECURRING,
        is_mission_aligned=False,
    )
    result = await service.preview_quote(command)
    assert result.discount_percent == Decimal("20")


@pytest.mark.asyncio
async def test_preview_quote_per_hour_surcharge():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={room_id: [make_rental_rate(facility_id=room_id)]},
        surcharges=[make_surcharge(charge_type=RentalSurchargeChargeType.PER_HOUR.value, unit_amount=Decimal("5"))],
    )
    service = _pricing_service(rental, {room_id})
    command = make_preview_quote_command(facility_id=room_id, billed_hours=Decimal("4"), surcharge_codes=["audio_system"])
    result = await service.preview_quote(command)
    assert result.surcharge_amount == Decimal("20.00")


@pytest.mark.asyncio
async def test_preview_quote_flat_surcharge():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={room_id: [make_rental_rate(facility_id=room_id)]},
        surcharges=[make_surcharge(charge_type=RentalSurchargeChargeType.FLAT.value, unit_amount=Decimal("25"))],
    )
    service = _pricing_service(rental, {room_id})
    command = make_preview_quote_command(facility_id=room_id, surcharge_codes=["audio_system"])
    result = await service.preview_quote(command)
    assert result.surcharge_amount == Decimal("25.00")


@pytest.mark.asyncio
async def test_preview_quote_unknown_surcharge_raises():
    room_id = new_uuid()
    rental = StubRentalRepository(rates_by_facility={room_id: [make_rental_rate(facility_id=room_id)]})
    service = _pricing_service(rental, {room_id})
    command = make_preview_quote_command(facility_id=room_id, surcharge_codes=["missing"])
    with pytest.raises(BadRequestException, match="Surcharge"):
        await service.preview_quote(command)


@pytest.mark.asyncio
async def test_preview_quote_applies_minimum_fee_floor():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={room_id: [make_rental_rate(facility_id=room_id, unit_amount=Decimal("1"))]},
        policy_amounts={
            (RentalPolicySettingKey.MINIMUM_FEE_DEFAULT.value, room_id): Decimal("100"),
        },
    )
    service = _pricing_service(rental, {room_id})
    result = await service.preview_quote(make_preview_quote_command(facility_id=room_id, billed_hours=Decimal("1")))
    assert result.quoted_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_preview_quote_quantizes_amounts():
    room_id = new_uuid()
    rental = StubRentalRepository(
        rates_by_facility={
            room_id: [
                make_rental_rate(
                    facility_id=room_id,
                    unit_amount=Decimal("10.333"),
                    billing_unit=RentalRateBillingUnit.HOURLY.value,
                )
            ]
        },
    )
    service = _pricing_service(rental, {room_id})
    result = await service.preview_quote(make_preview_quote_command(facility_id=room_id, billed_hours=Decimal("1.5")))
    assert result.subtotal_amount == Decimal("15.50")
