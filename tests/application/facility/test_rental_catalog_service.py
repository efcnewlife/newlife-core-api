"""
RentalCatalogService unit tests.
"""
from uuid import uuid4

import pytest

from portal.application.facility.commands import DeleteCommand, UpdateDiscountRuleCommand, UpdateSurchargeCommand
from portal.application.facility.rental_catalog_service import RentalCatalogService
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
    command = UpdateSurchargeCommand(
        code="audio",
        charge_type="flat",
        unit_amount=10,
    )
    with pytest.raises(NotFoundException):
        await service.update_surcharge(uuid4(), command)
