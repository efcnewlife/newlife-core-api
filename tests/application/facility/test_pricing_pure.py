"""
Pure pricing logic tests (no async, no DB).
"""
from decimal import Decimal
from uuid import uuid4

from portal.application.facility.pricing_service import PricingService
from portal.domain.facility.constants import RentalRateBillingUnit
from portal.infrastructure.persistence.repositories.facility.rental_repository import RentalRepository
from tests.fixtures.facility.factories import make_hourly_and_daily_rates, make_rental_rate


def test_pick_rate_for_line_uses_daily_flat_at_threshold():
    facility_id = uuid4()
    rates = make_hourly_and_daily_rates(facility_id, daily_amount=Decimal("200"))
    rate, tier = RentalRepository.pick_rate_for_line(
        rates=rates,
        billed_hours=Decimal("5"),
    )
    assert tier == RentalRateBillingUnit.DAILY_FLAT.value
    assert rate.billing_unit == RentalRateBillingUnit.DAILY_FLAT.value


def test_pick_rate_for_line_uses_hourly_below_threshold():
    facility_id = uuid4()
    rates = make_hourly_and_daily_rates(facility_id)
    rate, tier = RentalRepository.pick_rate_for_line(
        rates=rates,
        billed_hours=Decimal("4.99"),
    )
    assert tier == RentalRateBillingUnit.HOURLY.value
    assert rate.billing_unit == RentalRateBillingUnit.HOURLY.value


def test_pick_rate_for_line_falls_back_to_default():
    facility_id = uuid4()
    default_rate = make_rental_rate(
        facility_id=facility_id,
        billing_unit=RentalRateBillingUnit.PER_SLOT.value,
        is_default=True,
    )
    inactive_hourly = make_rental_rate(
        facility_id=facility_id,
        billing_unit=RentalRateBillingUnit.HOURLY.value,
        is_active=False,
        applicability={"all": [{"op": "hours_lt", "value": 5}]},
    )
    rate, tier = RentalRepository.pick_rate_for_line(
        rates=[inactive_hourly, default_rate],
        billed_hours=Decimal("1"),
    )
    assert rate.id == default_rate.id
    assert tier == RentalRateBillingUnit.PER_SLOT.value


def test_compute_line_subtotal_daily_flat():
    total = PricingService._compute_line_subtotal(
        RentalRateBillingUnit.DAILY_FLAT.value,
        Decimal("200"),
        Decimal("6"),
    )
    assert total == Decimal("200")


def test_compute_line_subtotal_hourly():
    total = PricingService._compute_line_subtotal(
        RentalRateBillingUnit.HOURLY.value,
        Decimal("10"),
        Decimal("6"),
    )
    assert total == Decimal("60")


def test_compute_line_subtotal_per_slot_and_flat_per_booking():
    per_slot = PricingService._compute_line_subtotal(
        RentalRateBillingUnit.PER_SLOT.value,
        Decimal("50"),
        Decimal("8"),
    )
    flat = PricingService._compute_line_subtotal(
        RentalRateBillingUnit.FLAT_PER_BOOKING.value,
        Decimal("75"),
        Decimal("8"),
    )
    assert per_slot == Decimal("50")
    assert flat == Decimal("75")
