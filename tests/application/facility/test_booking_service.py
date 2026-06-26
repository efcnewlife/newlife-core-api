"""
BookingService unit tests.
"""
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingRoomLineCommand, CancelBookingCommand
from portal.application.facility.results import BookingDetailResult
from portal.domain.facility.constants import RentalPolicySettingKey
from portal.exceptions.responses import BadRequestException, NotFoundException
from tests.fixtures.facility.factories import (
    make_preview_quote_result,
    make_update_booking_command,
    new_uuid,
)
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubPricingService,
    StubRentalRepository,
)


def _booking_service(
    booking_stub: StubBookingRepository,
    rental_stub: StubRentalRepository | None = None,
    pricing_stub: StubPricingService | None = None,
) -> BookingService:
    quote = make_preview_quote_result(quoted_amount=Decimal("150"), discount_percent=Decimal("10"))
    return BookingService(
        booking_stub,
        pricing_stub or StubPricingService(quote),
        rental_stub or StubRentalRepository(),
    )


@pytest.mark.asyncio
async def test_cancel_booking_not_found():
    service = _booking_service(StubBookingRepository(exists=False))
    with pytest.raises(NotFoundException, match="Booking not found"):
        await service.cancel_booking(uuid4(), CancelBookingCommand())


@pytest.mark.asyncio
async def test_cancel_booking_series_scope_skips_slot_cancel():
    booking_id = uuid4()
    stub = StubBookingRepository(exists=True)
    service = _booking_service(stub)
    await service.cancel_booking(booking_id, CancelBookingCommand(scope="series", cancel_reason="test"))
    assert stub.cancel_calls[0]["cancel_slots"] is False


@pytest.mark.asyncio
async def test_cancel_booking_single_scope_cancels_slots():
    booking_id = uuid4()
    stub = StubBookingRepository(exists=True)
    service = _booking_service(stub)
    await service.cancel_booking(booking_id, CancelBookingCommand(scope="single"))
    assert stub.cancel_calls[0]["cancel_slots"] is True


@pytest.mark.asyncio
async def test_update_booking_invalid_time_range():
    room_id = new_uuid()
    command = make_update_booking_command(
        facility_id=room_id,
        start_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
    )
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException, match="end_at"):
        await service.update_booking(uuid4(), command)


@pytest.mark.asyncio
async def test_update_booking_requires_rooms():
    service = _booking_service(StubBookingRepository())
    command = make_update_booking_command()
    command.rooms = []
    with pytest.raises(BadRequestException, match="At least one room"):
        await service.update_booking(uuid4(), command)


@pytest.mark.asyncio
async def test_update_booking_max_rooms_exceeded():
    room_ids = [new_uuid(), new_uuid(), new_uuid()]
    rental = StubRentalRepository(
        policy_amounts={(RentalPolicySettingKey.MAX_ROOMS_PER_BOOKING.value, None): Decimal("2")},
    )
    command = make_update_booking_command()
    command.rooms = [
        BookingRoomLineCommand(facility_id=room_id, sequence=idx)
        for idx, room_id in enumerate(room_ids)
    ]
    service = _booking_service(StubBookingRepository(), rental)
    with pytest.raises(BadRequestException, match="At most 2"):
        await service.update_booking(uuid4(), command)


@pytest.mark.asyncio
async def test_update_booking_slot_overlap_conflict():
    room_id = new_uuid()
    stub = StubBookingRepository(has_overlap=True)
    service = _booking_service(stub)
    with pytest.raises(BadRequestException, match="scheduling conflict"):
        await service.update_booking(uuid4(), make_update_booking_command(facility_id=room_id))


@pytest.mark.asyncio
async def test_update_booking_persists_quote_on_header():
    booking_id = uuid4()
    room_id = new_uuid()
    quote = make_preview_quote_result(quoted_amount=Decimal("150"), discount_percent=Decimal("10"))
    booking_stub = StubBookingRepository(
        exists=True,
        detail=BookingDetailResult(
            id=booking_id,
            user_id=uuid4(),
            booking_type="one_time",
            start_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
            status="confirmed",
            quoted_amount=quote.quoted_amount,
        ),
    )
    service = _booking_service(booking_stub, pricing_stub=StubPricingService(quote))
    await service.update_booking(booking_id, make_update_booking_command(facility_id=room_id))
    header = booking_stub.update_header_calls[0]
    assert header["quoted_amount"] == Decimal("150")
    assert header["discount_percent"] == Decimal("10")
    assert len(booking_stub.replace_rooms_calls[0]) == 1


def test_billed_hours_rounds_to_two_decimal_places():
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    assert BookingService._billed_hours(start, end) == Decimal("2.00")
