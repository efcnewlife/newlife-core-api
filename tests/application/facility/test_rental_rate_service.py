"""
RentalRateService unit tests.
"""

import pytest

from portal.application.facility.commands import DeleteCommand, UpdateRentalRateCommand
from portal.application.facility.rental_rate_service import RentalRateService
from portal.exceptions.responses import ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_rental_rate_command, make_rental_rate, make_rental_rate_template, new_uuid
from tests.fixtures.facility.stubs import StubRentalRepository, StubRoomRepository


@pytest.mark.asyncio
async def test_create_rate_room_not_found():
    facility_id = new_uuid()
    template_id = new_uuid()
    rental = StubRentalRepository()
    rental.templates_by_id[template_id] = make_rental_rate_template(template_id=template_id)
    service = RentalRateService(rental, StubRoomRepository())
    with pytest.raises(NotFoundException):
        await service.create_rate(make_create_rental_rate_command(facility_id, template_id))


@pytest.mark.asyncio
async def test_create_rate_success():
    facility_id = new_uuid()
    template_id = new_uuid()
    rental = StubRentalRepository()
    rental.templates_by_id[template_id] = make_rental_rate_template(template_id=template_id)
    room = StubRoomRepository(existing_ids={facility_id})
    service = RentalRateService(rental, room)
    result = await service.create_rate(make_create_rental_rate_command(facility_id, template_id))
    assert result.id is not None
    assert len(rental.insert_rate_calls) == 1
    assert rental.insert_rate_calls[0]["template_id"] == template_id
    assert rental.insert_rate_calls[0]["facility_id"] == facility_id
    assert "unit_amount" not in rental.insert_rate_calls[0]


@pytest.mark.asyncio
async def test_create_rate_unique_conflict():
    facility_id = new_uuid()
    template_id = new_uuid()
    rental = StubRentalRepository(insert_raises_unique=True)
    rental.templates_by_id[template_id] = make_rental_rate_template(template_id=template_id)
    room = StubRoomRepository(existing_ids={facility_id})
    service = RentalRateService(rental, room)
    with pytest.raises(ConflictErrorException):
        await service.create_rate(make_create_rental_rate_command(facility_id, template_id))


@pytest.mark.asyncio
async def test_update_rate_not_found():
    service = RentalRateService(StubRentalRepository(), StubRoomRepository(existing_ids={new_uuid()}))
    command = UpdateRentalRateCommand(facility_id=new_uuid(), template_id=new_uuid())
    with pytest.raises(NotFoundException):
        await service.update_rate(new_uuid(), command)


@pytest.mark.asyncio
async def test_update_rate_success():
    rate_id = new_uuid()
    facility_id = new_uuid()
    template_id = new_uuid()
    rental = StubRentalRepository()
    rental.rates_by_id[rate_id] = make_rental_rate(facility_id=facility_id, rate_id=rate_id)
    rental.templates_by_id[template_id] = make_rental_rate_template(template_id=template_id)
    service = RentalRateService(rental, StubRoomRepository(existing_ids={facility_id}))
    await service.update_rate(rate_id, UpdateRentalRateCommand(facility_id=facility_id, template_id=template_id, is_active=False))


@pytest.mark.asyncio
async def test_delete_rate_soft():
    rate_id = new_uuid()
    facility_id = new_uuid()
    rental = StubRentalRepository()
    rental.rates_by_id[rate_id] = make_rental_rate(facility_id=facility_id, rate_id=rate_id)
    service = RentalRateService(rental, StubRoomRepository())
    await service.delete_rate(rate_id, DeleteCommand(reason="cleanup"))


@pytest.mark.asyncio
async def test_get_rate_not_found():
    service = RentalRateService(StubRentalRepository(), StubRoomRepository())
    assert await service.get_rate_by_id(new_uuid()) is None
