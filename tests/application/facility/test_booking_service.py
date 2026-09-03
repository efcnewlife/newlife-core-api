"""
BookingService unit tests.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import (
    BookingRangeQueryCommand,
    BookingRoomLineCommand,
    CancelBookingCommand,
    MemberPreviewQuoteCommand,
    MemberPreviewQuoteLineCommand,
    PreviewQuoteCommand,
    PreviewQuoteRoomLineCommand,
)
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.results import BookingDetailResult, BookingRoomLineResult, PreviewQuoteRoomLineResult
from portal.domain.facility.constants import BookingStatus, BookingType, RentalPolicySettingKey
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException, NotFoundException
from tests.fixtures.facility.factories import (
    make_booking_list_item,
    make_create_booking_command,
    make_hourly_and_daily_rates,
    make_ministry_detail,
    make_preview_quote_result,
    make_update_booking_command,
    new_uuid,
)
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubPricingService,
    StubRentalRepository,
    StubRoomBlackoutRepository,
    StubRoomRepository,
)
from tests.fixtures.system.stubs import StubSettingService


def _user_ctx(monkeypatch, *, user_id=None):
    user_id = user_id or uuid4()

    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: ctx)
    return ctx


def _booking_service(
    booking_stub: StubBookingRepository,
    rental_stub: StubRentalRepository | None = None,
    pricing_stub: StubPricingService | None = None,
    blackout_stub: StubRoomBlackoutRepository | None = None,
    ministry_stub: StubMinistryRepository | None = None,
) -> BookingService:
    quote = make_preview_quote_result(quoted_amount=Decimal("150"), discount_percent=Decimal("10"))
    return BookingService(
        booking_stub,
        pricing_stub or StubPricingService(quote),
        rental_stub or StubRentalRepository(),
        ministry_stub or StubMinistryRepository(),
        blackout_stub or StubRoomBlackoutRepository(),
        StubSettingService(),
    )


@pytest.mark.asyncio
async def test_cancel_booking_not_found():
    service = _booking_service(StubBookingRepository(exists=False))
    with pytest.raises(NotFoundException) as exc_info:
        await service.cancel_booking(uuid4(), CancelBookingCommand())
    assert exc_info.value.error_code == "FACILITY_BOOKING_NOT_FOUND"


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
        facility_id=room_id, start_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    )
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_booking(uuid4(), command)
    assert "end_at" in str(exc_info.value.detail)
    assert exc_info.value.error_code == "FACILITY_BOOKING_INVALID_TIME_RANGE"


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
    rental = StubRentalRepository(policy_amounts={(RentalPolicySettingKey.MAX_ROOMS_PER_BOOKING.value, None): Decimal("2")})
    command = make_update_booking_command()
    command.rooms = [BookingRoomLineCommand(facility_id=room_id, sequence=idx) for idx, room_id in enumerate(room_ids)]
    service = _booking_service(StubBookingRepository(), rental)
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_booking(uuid4(), command)
    assert "At most 2" in str(exc_info.value.detail)
    assert exc_info.value.error_code == "FACILITY_BOOKING_MAX_ROOMS"


@pytest.mark.asyncio
async def test_update_booking_slot_overlap_conflict():
    room_id = new_uuid()
    stub = StubBookingRepository(has_overlap=True)
    service = _booking_service(stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.update_booking(uuid4(), make_update_booking_command(facility_id=room_id))
    exc = exc_info.value
    assert exc.status_code == 409
    assert exc.error_code == "FACILITY_BOOKING_SCHEDULING_CONFLICT"
    assert exc.context == {"facility_id": str(room_id)}
    assert "scheduling conflict" in str(exc.detail)


@pytest.mark.asyncio
async def test_update_booking_blackout_conflict():
    room_id = new_uuid()
    stub = StubBookingRepository(has_overlap=False)
    service = _booking_service(stub, blackout_stub=StubRoomBlackoutRepository(has_overlap=True))
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_booking(uuid4(), make_update_booking_command(facility_id=room_id))
    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.error_code == "FACILITY_BOOKING_ROOM_BLACKOUT"
    assert exc.context == {"facility_id": str(room_id)}
    assert "closed for the selected time" in str(exc.detail)


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


@pytest.mark.asyncio
async def test_create_booking_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: None)
    service = _booking_service(StubBookingRepository())
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.create_booking(make_create_booking_command())


@pytest.mark.asyncio
async def test_create_booking_uses_command_booker_when_set(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    _user_ctx(monkeypatch, user_id=operator_id)
    stub = StubBookingRepository()
    service = _booking_service(stub)
    result = await service.create_booking(make_create_booking_command(user_id=booker_id))
    assert result.id is not None
    assert stub.insert_calls[0]["user_id"] == booker_id
    assert stub.insert_calls[0]["user_id"] != operator_id
    assert stub.insert_calls[0]["status"] == "confirmed"
    assert stub.insert_calls[0]["booking_type"] == "one_time"
    assert len(stub.replace_rooms_calls[0]) == 1


@pytest.mark.asyncio
async def test_create_booking_uses_user_context_when_booker_omitted(monkeypatch):
    operator_id = uuid4()
    _user_ctx(monkeypatch, user_id=operator_id)
    stub = StubBookingRepository()
    service = _booking_service(stub)
    await service.create_booking(make_create_booking_command())
    assert stub.insert_calls[0]["user_id"] == operator_id


@pytest.mark.asyncio
async def test_create_booking_ministry_membership_checked_on_booker(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    ministry = make_ministry_detail()
    _user_ctx(monkeypatch, user_id=operator_id)
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={booker_id})
    stub = StubBookingRepository()
    service = _booking_service(stub, ministry_stub=ministry_stub)
    await service.create_booking(make_create_booking_command(user_id=booker_id, ministry_id=ministry.id))
    assert ministry_stub.membership_check_calls[0]["user_id"] == booker_id


@pytest.mark.asyncio
async def test_create_booking_rejects_when_booker_not_ministry_member(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    ministry = make_ministry_detail()
    _user_ctx(monkeypatch, user_id=operator_id)
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={operator_id})
    service = _booking_service(StubBookingRepository(), ministry_stub=ministry_stub)
    with pytest.raises(ForbiddenException, match="not a ministry owner"):
        await service.create_booking(make_create_booking_command(user_id=booker_id, ministry_id=ministry.id))


@pytest.mark.asyncio
async def test_create_booking_slot_overlap_conflict(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    service = _booking_service(StubBookingRepository(has_overlap=True))
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_booking(make_create_booking_command(facility_id=room_id))
    exc = exc_info.value
    assert exc.status_code == 409
    assert exc.error_code == "FACILITY_BOOKING_SCHEDULING_CONFLICT"
    assert exc.context == {"facility_id": str(room_id)}
    assert "scheduling conflict" in str(exc.detail)


@pytest.mark.asyncio
async def test_create_booking_blackout_conflict(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    service = _booking_service(StubBookingRepository(has_overlap=False), blackout_stub=StubRoomBlackoutRepository(has_overlap=True))
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(make_create_booking_command(facility_id=room_id))
    exc = exc_info.value
    assert exc.status_code == 400
    assert exc.error_code == "FACILITY_BOOKING_ROOM_BLACKOUT"
    assert exc.context == {"facility_id": str(room_id)}
    assert "closed for the selected time" in str(exc.detail)


@pytest.mark.asyncio
async def test_create_booking_max_rooms_exceeded(monkeypatch):
    _user_ctx(monkeypatch)
    room_ids = [new_uuid(), new_uuid(), new_uuid()]
    rental = StubRentalRepository(policy_amounts={(RentalPolicySettingKey.MAX_ROOMS_PER_BOOKING.value, None): Decimal("2")})
    command = make_create_booking_command()
    command.rooms = [BookingRoomLineCommand(facility_id=room_id, sequence=idx) for idx, room_id in enumerate(room_ids)]
    service = _booking_service(StubBookingRepository(), rental)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(command)
    assert "At most 2" in str(exc_info.value.detail)
    assert exc_info.value.error_code == "FACILITY_BOOKING_MAX_ROOMS"


@pytest.mark.asyncio
async def test_create_booking_invalid_time_range_has_error_code(monkeypatch):
    _user_ctx(monkeypatch)
    command = make_create_booking_command(start_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc))
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(command)
    assert "end_at" in str(exc_info.value.detail)
    assert exc_info.value.error_code == "FACILITY_BOOKING_INVALID_TIME_RANGE"


@pytest.mark.asyncio
async def test_create_booking_two_lines_same_room_different_times(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    morning_start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    morning_end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    afternoon_start = datetime(2026, 5, 1, 18, 0, tzinfo=timezone.utc)
    afternoon_end = datetime(2026, 5, 1, 20, 0, tzinfo=timezone.utc)
    command = make_create_booking_command(facility_id=room_id, start_at=morning_start, end_at=afternoon_end)
    command.rooms = [
        BookingRoomLineCommand(facility_id=room_id, start_at=morning_start, end_at=morning_end, sequence=0),
        BookingRoomLineCommand(facility_id=room_id, start_at=afternoon_start, end_at=afternoon_end, sequence=1),
    ]
    stub = StubBookingRepository()
    quote = make_preview_quote_result(quoted_amount=Decimal("150"))
    quote.room_lines = [
        PreviewQuoteRoomLineResult(
            facility_id=room_id,
            billed_hours=Decimal("2.00"),
            rental_rate_name="Hourly",
            billing_unit="hourly",
            unit_amount=Decimal("10"),
            currency="CAD",
            applicability=None,
            is_default=True,
            line_subtotal=Decimal("75"),
        ),
        PreviewQuoteRoomLineResult(
            facility_id=room_id,
            billed_hours=Decimal("2.00"),
            rental_rate_name="Hourly",
            billing_unit="hourly",
            unit_amount=Decimal("10"),
            currency="CAD",
            applicability=None,
            is_default=True,
            line_subtotal=Decimal("75"),
        ),
    ]
    service = _booking_service(stub, pricing_stub=StubPricingService(quote))
    result = await service.create_booking(command)
    assert result.id is not None
    assert stub.insert_calls[0]["facility_id"] == room_id
    assert stub.insert_calls[0]["start_at"] == morning_start
    assert stub.insert_calls[0]["end_at"] == afternoon_end
    assert len(stub.replace_rooms_calls[0]) == 2
    assert stub.replace_rooms_calls[0][0]["facility_id"] == room_id
    assert stub.replace_rooms_calls[0][1]["facility_id"] == room_id


@pytest.mark.asyncio
async def test_create_booking_rejects_fourth_line(monkeypatch):
    _user_ctx(monkeypatch)
    room_ids = [new_uuid() for _ in range(4)]
    command = make_create_booking_command()
    command.rooms = [BookingRoomLineCommand(facility_id=room_id, sequence=idx) for idx, room_id in enumerate(room_ids)]
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_MAX_ROOMS"


@pytest.mark.asyncio
async def test_create_booking_rejects_cross_midnight_line(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    command = make_create_booking_command(facility_id=room_id)
    command.rooms = [
        BookingRoomLineCommand(
            facility_id=room_id, start_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc), sequence=0
        )
    ]
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINE_CROSS_MIDNIGHT"


@pytest.mark.asyncio
async def test_create_booking_scheduling_conflict_is_first_fail(monkeypatch):
    _user_ctx(monkeypatch)
    first_room_id = new_uuid()
    second_room_id = new_uuid()

    class FirstRoomOverlapRepository(StubBookingRepository):
        async def has_confirmed_slot_overlap(self, facility_id, start_at, end_at, exclude_booking_id=None):
            return facility_id == first_room_id

    command = make_create_booking_command(facility_id=first_room_id)
    command.rooms = [BookingRoomLineCommand(facility_id=first_room_id, sequence=0), BookingRoomLineCommand(facility_id=second_room_id, sequence=1)]
    service = _booking_service(FirstRoomOverlapRepository())
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_booking(command)
    assert exc_info.value.context == {"facility_id": str(first_room_id)}
    assert exc_info.value.error_code == "FACILITY_BOOKING_SCHEDULING_CONFLICT"


@pytest.mark.asyncio
async def test_get_booking_range_rejects_oversize_window():
    date_from = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    date_to = date_from + timedelta(days=62, seconds=1)
    service = _booking_service(StubBookingRepository())
    with pytest.raises(BadRequestException) as exc_info:
        await service.get_booking_range(BookingRangeQueryCommand(date_from=date_from, date_to=date_to))
    assert exc_info.value.error_code == "FACILITY_BOOKING_RANGE_WINDOW_TOO_LARGE"


@pytest.mark.asyncio
async def test_get_booking_range_includes_bookings_that_span_window_edge():
    """Overlap match: booking starts before window and ends inside; start-in-window alone would miss it."""
    window_start = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc)
    spanning = make_booking_list_item(
        start_at=datetime(2026, 4, 30, 22, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 1, 2, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value
    )
    starts_inside = make_booking_list_item(
        start_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value
    )
    entirely_before = make_booking_list_item(
        start_at=datetime(2026, 4, 29, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED.value,
    )
    stub = StubBookingRepository(range_items=[spanning, starts_inside, entirely_before])
    service = _booking_service(stub)
    result = await service.get_booking_range(BookingRangeQueryCommand(date_from=window_start, date_to=window_end))
    returned_ids = {item.id for item in result.items}
    assert spanning.id in returned_ids
    assert starts_inside.id in returned_ids
    assert entirely_before.id not in returned_ids


@pytest.mark.asyncio
async def test_get_booking_range_excludes_cancelled_by_default():
    window_start = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc)
    confirmed = make_booking_list_item(
        start_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value
    )
    cancelled = make_booking_list_item(
        start_at=datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CANCELLED.value
    )
    stub = StubBookingRepository(range_items=[confirmed, cancelled])
    service = _booking_service(stub)
    result = await service.get_booking_range(BookingRangeQueryCommand(date_from=window_start, date_to=window_end))
    returned_ids = {item.id for item in result.items}
    assert confirmed.id in returned_ids
    assert cancelled.id not in returned_ids


@pytest.mark.asyncio
async def test_get_booking_range_include_cancelled_flag():
    window_start = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc)
    cancelled = make_booking_list_item(
        start_at=datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CANCELLED.value
    )
    stub = StubBookingRepository(range_items=[cancelled])
    service = _booking_service(stub)
    result = await service.get_booking_range(BookingRangeQueryCommand(date_from=window_start, date_to=window_end, include_cancelled=True))
    assert {item.id for item in result.items} == {cancelled.id}


@pytest.mark.asyncio
async def test_get_booking_range_excludes_soft_deleted():
    window_start = datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)
    window_end = datetime(2026, 5, 8, 0, 0, tzinfo=timezone.utc)
    active = make_booking_list_item(
        start_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value
    )
    deleted = make_booking_list_item(
        start_at=datetime(2026, 5, 3, 10, 0, tzinfo=timezone.utc), end_at=datetime(2026, 5, 3, 12, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value
    )
    stub = StubBookingRepository(range_items=[active, deleted], deleted_ids={deleted.id})
    service = _booking_service(stub)
    result = await service.get_booking_range(BookingRangeQueryCommand(date_from=window_start, date_to=window_end))
    returned_ids = {item.id for item in result.items}
    assert active.id in returned_ids
    assert deleted.id not in returned_ids


def _booking_detail(*, booking_id, user_id, quoted_amount=Decimal("85")) -> BookingDetailResult:
    start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    room_id = uuid4()
    return BookingDetailResult(
        id=booking_id,
        user_id=user_id,
        booking_type="one_time",
        start_at=start,
        end_at=end,
        status="confirmed",
        quoted_amount=quoted_amount,
        currency="CAD",
        rooms=[BookingRoomLineResult(id=uuid4(), facility_id=room_id, start_at=start, end_at=end, sequence=0)],
    )


@pytest.mark.asyncio
async def test_booker_can_read_own_quoted_amount(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    detail = _booking_detail(booking_id=booking_id, user_id=owner_id, quoted_amount=Decimal("85"))
    service = _booking_service(StubBookingRepository(detail=detail))
    result = await service.get_my_booking_by_id(booking_id)
    assert result.quoted_amount == Decimal("85")
    assert result.currency == "CAD"


@pytest.mark.asyncio
async def test_booker_cannot_read_another_bookers_booking(monkeypatch):
    _user_ctx(monkeypatch, user_id=uuid4())
    other_booking_id = uuid4()
    detail = _booking_detail(booking_id=other_booking_id, user_id=uuid4(), quoted_amount=Decimal("85"))
    service = _booking_service(StubBookingRepository(detail=detail))
    with pytest.raises(NotFoundException) as exc_info:
        await service.get_my_booking_by_id(other_booking_id)
    assert exc_info.value.error_code == "FACILITY_BOOKING_NOT_FOUND"


@pytest.mark.asyncio
async def test_preview_quote_for_member_honors_ministry_gate(monkeypatch):
    user_id = uuid4()
    _user_ctx(monkeypatch, user_id=user_id)
    ministry_id = uuid4()
    ministry = make_ministry_detail(ministry_id)
    service = _booking_service(
        StubBookingRepository(), ministry_stub=StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    )
    room_id = uuid4()
    start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    command = MemberPreviewQuoteCommand(
        is_mission_aligned=True, ministry_id=ministry_id, lines=[MemberPreviewQuoteLineCommand(facility_id=room_id, start_at=start, end_at=end)]
    )
    result = await service.preview_quote_for_member(command)
    assert result.quoted_amount == Decimal("150")
    assert service._pricing_service.preview_calls[-1].is_mission_aligned is True
    assert service._pricing_service.preview_calls[-1].ministry_id == ministry_id


@pytest.mark.asyncio
async def test_preview_quote_for_member_passes_per_line_billed_hours(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    service = _booking_service(StubBookingRepository())
    command = MemberPreviewQuoteCommand(
        lines=[
            MemberPreviewQuoteLineCommand(
                facility_id=room_id, start_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc)
            ),
            MemberPreviewQuoteLineCommand(
                facility_id=room_id, start_at=datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
            ),
        ]
    )
    await service.preview_quote_for_member(command)
    preview_command = service._pricing_service.preview_calls[-1]
    assert preview_command.room_lines[0].billed_hours == Decimal("2.00")
    assert preview_command.room_lines[1].billed_hours == Decimal("4.00")


@pytest.mark.asyncio
async def test_preview_quote_for_member_same_room_different_subtotals(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    rental = StubRentalRepository(rates_by_facility={room_id: make_hourly_and_daily_rates(room_id, hourly_amount=Decimal("10"))})
    pricing = PricingService(rental, StubRoomRepository(existing_ids={room_id}))
    service = BookingService(StubBookingRepository(), pricing, rental, StubMinistryRepository(), StubRoomBlackoutRepository(), StubSettingService())
    command = MemberPreviewQuoteCommand(
        lines=[
            MemberPreviewQuoteLineCommand(
                facility_id=room_id, start_at=datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 11, 0, tzinfo=timezone.utc)
            ),
            MemberPreviewQuoteLineCommand(
                facility_id=room_id, start_at=datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc), end_at=datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
            ),
        ]
    )
    result = await service.preview_quote_for_member(command)
    assert result.room_lines[0].line_subtotal == Decimal("20.00")
    assert result.room_lines[1].line_subtotal == Decimal("40.00")
    assert result.subtotal_amount == Decimal("60.00")


@pytest.mark.asyncio
async def test_preview_quote_for_member_rejects_duplicate_line(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    service = _booking_service(StubBookingRepository())
    start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    command = MemberPreviewQuoteCommand(
        lines=[
            MemberPreviewQuoteLineCommand(facility_id=room_id, start_at=start, end_at=end),
            MemberPreviewQuoteLineCommand(facility_id=room_id, start_at=start, end_at=end),
        ]
    )
    with pytest.raises(BadRequestException) as exc_info:
        await service.preview_quote_for_member(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_DUPLICATE_LINE"


@pytest.mark.asyncio
async def test_preview_quote_for_member_rejects_non_steward(monkeypatch):
    _user_ctx(monkeypatch, user_id=uuid4())
    ministry_id = uuid4()
    ministry = make_ministry_detail(ministry_id)
    service = _booking_service(
        StubBookingRepository(), ministry_stub=StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids=set())
    )
    start = datetime(2026, 8, 22, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 8, 22, 18, 0, tzinfo=timezone.utc)
    command = MemberPreviewQuoteCommand(ministry_id=ministry_id, lines=[MemberPreviewQuoteLineCommand(facility_id=uuid4(), start_at=start, end_at=end)])
    with pytest.raises(ForbiddenException):
        await service.preview_quote_for_member(command)
