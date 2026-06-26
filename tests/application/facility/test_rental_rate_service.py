"""
RentalRateService unit tests.
"""
from uuid import uuid4

import pytest

from portal.application.facility.commands import DeleteCommand, UpdateRentalRateCommand
from portal.application.facility.rental_rate_service import RentalRateService
from portal.domain.facility.constants import RentalRateBillingUnit
from portal.exceptions.responses import ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_rental_rate_command, new_uuid
from tests.fixtures.facility.stubs import StubRentalRepository, StubRoomRepository


@pytest.mark.asyncio
async def test_create_rate_room_not_found():
    facility_id = new_uuid()
    service = RentalRateService(StubRentalRepository(), StubRoomRepository())
    with pytest.raises(NotFoundException, match="Room"):
        await service.create_rate(make_create_rental_rate_command(facility_id))


@pytest.mark.asyncio
async def test_create_rate_success():
    facility_id = new_uuid()
    rental = StubRentalRepository()
    room = StubRoomRepository(existing_ids={facility_id})
    service = RentalRateService(rental, room)
    result = await service.create_rate(make_create_rental_rate_command(facility_id))
    assert len(rental.insert_rate_calls) == 1
    assert result.id is not None


@pytest.mark.asyncio
async def test_create_rate_unique_violation():
    facility_id = new_uuid()
    rental = StubRentalRepository(insert_raises_unique=True)
    room = StubRoomRepository(existing_ids={facility_id})
    service = RentalRateService(rental, room)
    with pytest.raises(ConflictErrorException, match="Rental rate"):
        await service.create_rate(make_create_rental_rate_command(facility_id))


@pytest.mark.asyncio
async def test_update_rate_not_found():
    facility_id = new_uuid()
    service = RentalRateService(StubRentalRepository(), StubRoomRepository(existing_ids={facility_id}))
    command = UpdateRentalRateCommand(
        facility_id=facility_id,
        billing_unit=RentalRateBillingUnit.HOURLY,
        unit_amount=10,
    )
    with pytest.raises(NotFoundException, match="Rental rate"):
        await service.update_rate(uuid4(), command)


@pytest.mark.asyncio
async def test_delete_rate_not_found():
    service = RentalRateService(StubRentalRepository(), StubRoomRepository())
    with pytest.raises(NotFoundException):
        await service.delete_rate(uuid4(), DeleteCommand(reason="x", permanent=False))
