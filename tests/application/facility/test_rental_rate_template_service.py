"""
RentalRateTemplateService unit tests.
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.commands import DeleteCommand
from portal.application.facility.rental_rate_template_service import RentalRateTemplateService
from portal.exceptions.responses import BadRequestException, ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_rental_rate_template_command, make_rental_rate_template, new_uuid
from tests.fixtures.facility.stubs import StubRentalRepository


@pytest.mark.asyncio
async def test_create_template_success():
    rental = StubRentalRepository()
    service = RentalRateTemplateService(rental)
    result = await service.create_template(make_create_rental_rate_template_command())
    assert result.id is not None
    assert len(rental.insert_template_calls) == 1
    assert rental.insert_template_calls[0]["unit_amount"] == Decimal("30")


@pytest.mark.asyncio
async def test_create_template_unique_conflict():
    rental = StubRentalRepository(insert_raises_unique=True)
    service = RentalRateTemplateService(rental)
    with pytest.raises(ConflictErrorException):
        await service.create_template(make_create_rental_rate_template_command())


@pytest.mark.asyncio
async def test_delete_template_blocked_when_rates_exist():
    template_id = new_uuid()
    rental = StubRentalRepository()
    rental.templates_by_id[template_id] = make_rental_rate_template(template_id=template_id)
    rental.count_rates_for_template_result = 1
    service = RentalRateTemplateService(rental)
    with pytest.raises(BadRequestException):
        await service.delete_template(template_id, DeleteCommand(reason="cleanup"))


@pytest.mark.asyncio
async def test_delete_template_not_found():
    service = RentalRateTemplateService(StubRentalRepository())
    with pytest.raises(NotFoundException):
        await service.delete_template(uuid4(), DeleteCommand(reason="cleanup"))
