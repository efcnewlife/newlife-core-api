"""
RentalCatalogService unit tests.
"""

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from portal.application.facility.commands import CreateDiscountRuleCommand, DeleteCommand, UpdateDiscountRuleCommand, UpdateSurchargeCommand
from portal.application.facility.rental_catalog_service import RentalCatalogService
from portal.cli.datas.facility_rental_seed_data import facility_discount_seed_rows
from portal.domain.facility.constants import RentalDiscountCode
from portal.exceptions.responses import ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_discount_command, make_create_surcharge_command, make_discount_rule
from tests.fixtures.facility.stubs import StubRentalRepository


@pytest.mark.asyncio
async def test_list_discount_rules_delegates_to_repository():
    rules = [make_discount_rule()]
    stub = StubRentalRepository(discount_rules=rules)
    service = RentalCatalogService(stub)
    result = await service.list_discount_rules()
    assert len(result.items) == 1


@pytest.mark.asyncio
async def test_create_discount_rule_success():
    stub = StubRentalRepository()
    service = RentalCatalogService(stub)
    result = await service.create_discount_rule(make_create_discount_command())
    assert len(stub.insert_discount_calls) == 1
    assert result.id is not None


def test_seeded_discount_rules_are_ministry_thirty_and_recurring_twenty():
    percents = {row["code"]: row["percent_off"] for row in facility_discount_seed_rows}
    assert percents[RentalDiscountCode.MISSION_ALIGNED.value] == Decimal("30.00")
    assert percents[RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value] == Decimal("20.00")
    assert all(row["is_active"] for row in facility_discount_seed_rows)


def test_create_discount_rule_rejects_percent_outside_zero_to_one_hundred():
    with pytest.raises(ValidationError):
        CreateDiscountRuleCommand(code="mission_aligned", percent_off=Decimal("100.01"))
    with pytest.raises(ValidationError):
        UpdateDiscountRuleCommand(code="mission_aligned", percent_off=Decimal("-1"))


def test_create_discount_rule_rejects_more_than_two_decimal_places():
    with pytest.raises(ValidationError):
        CreateDiscountRuleCommand(code="mission_aligned", percent_off=Decimal("30.001"))


@pytest.mark.asyncio
async def test_create_discount_rule_accepts_boundary_percents():
    stub = StubRentalRepository()
    service = RentalCatalogService(stub)
    await service.create_discount_rule(make_create_discount_command())
    await service.create_discount_rule(CreateDiscountRuleCommand(code="recurring_weekly_monthly", percent_off=Decimal("0.00")))
    await service.update_discount_rule(uuid4(), UpdateDiscountRuleCommand(code="mission_aligned", percent_off=Decimal("100.00")))
    assert stub.insert_discount_calls[1]["percent_off"] == Decimal("0.00")


@pytest.mark.asyncio
async def test_create_discount_rule_unique_violation():
    stub = StubRentalRepository(insert_raises_unique=True)
    service = RentalCatalogService(stub)
    with pytest.raises(ConflictErrorException, match="Discount rule code"):
        await service.create_discount_rule(make_create_discount_command())


@pytest.mark.asyncio
async def test_update_discount_rule_not_found():
    stub = StubRentalRepository(update_discount_affected=0)
    service = RentalCatalogService(stub)
    command = UpdateDiscountRuleCommand(code="x", percent_off=10)
    with pytest.raises(NotFoundException):
        await service.update_discount_rule(uuid4(), command)


@pytest.mark.asyncio
async def test_create_surcharge_unique_violation():
    stub = StubRentalRepository(insert_raises_unique=True)
    service = RentalCatalogService(stub)
    with pytest.raises(ConflictErrorException, match="Surcharge code"):
        await service.create_surcharge(make_create_surcharge_command())


@pytest.mark.asyncio
async def test_delete_surcharge_not_found():
    service = RentalCatalogService(StubRentalRepository())
    with pytest.raises(NotFoundException):
        await service.delete_surcharge(uuid4(), DeleteCommand(reason="x", permanent=False))


@pytest.mark.asyncio
async def test_update_surcharge_not_found():
    stub = StubRentalRepository(update_surcharge_affected=0)
    service = RentalCatalogService(stub)
    command = UpdateSurchargeCommand(code="audio", charge_type="flat", unit_amount=10)
    with pytest.raises(NotFoundException):
        await service.update_surcharge(uuid4(), command)
