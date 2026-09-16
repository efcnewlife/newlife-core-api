"""
BookingDraftService unit tests (ADR 0018).
"""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.booking_draft_service import BookingDraftService
from portal.application.facility.commands import BookingDraftLineCommand, CreateBookingDraftCommand, UpdateBookingDraftCommand
from portal.application.facility.results import BookingDraftDetailResult, BookingDraftStoredLineResult
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from tests.fixtures.facility.factories import make_create_booking_draft_command, make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import StubBookingDraftRepository, StubBookingRepository, StubPricingService, StubRoomBlackoutRepository
from tests.fixtures.system.stubs import StubSettingService


def _stored_draft(*, draft_id, user_id, date_, lines: list[BookingDraftStoredLineResult] | None = None) -> BookingDraftDetailResult:
    return BookingDraftDetailResult(id=draft_id, user_id=user_id, date=date_, ministry_id=None, lines=lines or [])


def _stored_line(*, facility_id, start_at, end_at, sequence: int = 0) -> BookingDraftStoredLineResult:
    return BookingDraftStoredLineResult(facility_id=facility_id, start_at=start_at, end_at=end_at, sequence=sequence)


def _user_ctx(monkeypatch, *, user_id=None):
    user_id = user_id or uuid4()

    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: ctx)
    return ctx


def _service(
    draft_stub: StubBookingDraftRepository | None = None,
    booking_stub: StubBookingRepository | None = None,
    blackout_stub: StubRoomBlackoutRepository | None = None,
    pricing_stub: StubPricingService | None = None,
    setting_stub: StubSettingService | None = None,
) -> BookingDraftService:
    quote = make_preview_quote_result(quoted_amount=Decimal("150"))
    return BookingDraftService(
        draft_stub or StubBookingDraftRepository(),
        booking_stub or StubBookingRepository(),
        blackout_stub or StubRoomBlackoutRepository(),
        pricing_stub or StubPricingService(quote),
        setting_stub or StubSettingService(),
    )


@pytest.mark.asyncio
async def test_create_draft_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: None)
    service = _service()
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.create_draft(make_create_booking_draft_command())


@pytest.mark.asyncio
async def test_create_draft_rejects_zero_lines(monkeypatch):
    _user_ctx(monkeypatch)
    service = _service()
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_draft(CreateBookingDraftCommand(lines=[]))
    assert exc_info.value.error_code == "FACILITY_BOOKING_ROOMS_REQUIRED"


@pytest.mark.asyncio
async def test_create_draft_rejects_lines_over_configured_cap(monkeypatch):
    _user_ctx(monkeypatch)
    cap = 3
    room_ids = [new_uuid() for _ in range(cap + 1)]
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc)
    command = CreateBookingDraftCommand(
        lines=[BookingDraftLineCommand(facility_id=room_id, start_at=start, end_at=end, sequence=idx) for idx, room_id in enumerate(room_ids)]
    )
    service = _service(setting_stub=StubSettingService(max_booking_lines=cap))
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_draft(command)
    assert f"At most {cap}" in str(exc_info.value.detail)
    assert exc_info.value.error_code == "FACILITY_BOOKING_MAX_ROOMS"


@pytest.mark.asyncio
async def test_create_draft_accepts_lines_up_to_configured_cap(monkeypatch):
    _user_ctx(monkeypatch)
    cap = 5
    room_ids = [new_uuid() for _ in range(cap)]
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc)
    command = CreateBookingDraftCommand(
        lines=[BookingDraftLineCommand(facility_id=room_id, start_at=start, end_at=end, sequence=idx) for idx, room_id in enumerate(room_ids)]
    )
    stub = StubBookingDraftRepository()
    service = _service(draft_stub=stub, setting_stub=StubSettingService(max_booking_lines=cap))
    result = await service.create_draft(command)
    assert result.id is not None
    assert len(stub.insert_lines_calls[0]) == cap


@pytest.mark.asyncio
async def test_create_draft_rejects_lines_spanning_more_than_one_day(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    command = CreateBookingDraftCommand(
        lines=[
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
                sequence=0,
            ),
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc),
                sequence=1,
            ),
        ]
    )
    service = _service()
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_draft(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINES_NOT_SAME_DAY"


@pytest.mark.asyncio
async def test_create_draft_rejects_cross_midnight_line(monkeypatch):
    _user_ctx(monkeypatch)
    room_id = new_uuid()
    command = CreateBookingDraftCommand(
        lines=[
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
                sequence=0,
            )
        ]
    )
    service = _service()
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_draft(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINE_CROSS_MIDNIGHT"


@pytest.mark.asyncio
async def test_create_draft_returns_id_and_persists_lines(monkeypatch):
    user_id = uuid4()
    _user_ctx(monkeypatch, user_id=user_id)
    stub = StubBookingDraftRepository()
    service = _service(draft_stub=stub)
    result = await service.create_draft(make_create_booking_draft_command())
    assert result.id is not None
    assert stub.insert_draft_calls[0]["user_id"] == user_id
    assert stub.insert_draft_calls[0]["date"] == datetime(2026, 5, 1).date()
    assert len(stub.insert_lines_calls[0]) == 1


@pytest.mark.asyncio
async def test_get_draft_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: None)
    service = _service()
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.get_draft(uuid4())


@pytest.mark.asyncio
async def test_get_draft_nonexistent_id_not_found(monkeypatch):
    _user_ctx(monkeypatch)
    service = _service()
    with pytest.raises(NotFoundException) as exc_info:
        await service.get_draft(uuid4())
    assert exc_info.value.error_code == "FACILITY_BOOKING_DRAFT_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_draft_another_members_draft_returns_same_not_found_response(monkeypatch):
    owner_id = uuid4()
    other_user_id = uuid4()
    draft_id = uuid4()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=owner_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=other_user_id)
    service = _service(draft_stub=stub)

    with pytest.raises(NotFoundException) as own_exc:
        await service.get_draft(uuid4())
    with pytest.raises(NotFoundException) as other_exc:
        await service.get_draft(draft_id)

    assert own_exc.value.error_code == other_exc.value.error_code == "FACILITY_BOOKING_DRAFT_NOT_FOUND"
    assert own_exc.value.status_code == other_exc.value.status_code


@pytest.mark.asyncio
async def test_get_draft_returns_lines_with_live_price_and_availability(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=start.date(), lines=[_stored_line(facility_id=room_id, start_at=start, end_at=end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    quote = make_preview_quote_result(quoted_amount=Decimal("75"))
    pricing_stub = StubPricingService(quote)
    service = _service(draft_stub=stub, pricing_stub=pricing_stub)

    result = await service.get_draft(draft_id)

    assert result.id == draft_id
    assert result.quoted_amount == Decimal("75")
    assert len(result.lines) == 1
    assert result.lines[0].is_available is True
    assert pricing_stub.preview_calls[-1].room_lines[0].facility_id == room_id
    assert pricing_stub.preview_calls[-1].room_lines[0].billed_hours == Decimal("2.00")


@pytest.mark.asyncio
async def test_get_draft_price_is_not_a_cached_creation_time_snapshot(monkeypatch):
    """Two GETs against the same stored lines must each call pricing live, not read a stored quote."""
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=start.date(), lines=[_stored_line(facility_id=room_id, start_at=start, end_at=end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    first_quote = make_preview_quote_result(quoted_amount=Decimal("75"))
    pricing_stub = StubPricingService(first_quote)
    service = _service(draft_stub=stub, pricing_stub=pricing_stub)

    first = await service.get_draft(draft_id)
    pricing_stub.quote_result = make_preview_quote_result(quoted_amount=Decimal("999"))
    second = await service.get_draft(draft_id)

    assert first.quoted_amount == Decimal("75")
    assert second.quoted_amount == Decimal("999")
    assert len(pricing_stub.preview_calls) == 2


@pytest.mark.asyncio
async def test_get_draft_line_unavailable_on_scheduling_conflict(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=start.date(), lines=[_stored_line(facility_id=room_id, start_at=start, end_at=end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub, booking_stub=StubBookingRepository(has_overlap=True))

    result = await service.get_draft(draft_id)
    assert result.lines[0].is_available is False


@pytest.mark.asyncio
async def test_get_draft_line_unavailable_on_blackout(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=start.date(), lines=[_stored_line(facility_id=room_id, start_at=start, end_at=end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub, blackout_stub=StubRoomBlackoutRepository(has_overlap=True))

    result = await service.get_draft(draft_id)
    assert result.lines[0].is_available is False


@pytest.mark.asyncio
async def test_update_draft_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: None)
    service = _service()
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.update_draft(uuid4(), UpdateBookingDraftCommand(lines=[]))


@pytest.mark.asyncio
async def test_update_draft_nonexistent_id_not_found(monkeypatch):
    _user_ctx(monkeypatch)
    service = _service()
    with pytest.raises(NotFoundException) as exc_info:
        await service.update_draft(uuid4(), UpdateBookingDraftCommand(lines=[]))
    assert exc_info.value.error_code == "FACILITY_BOOKING_DRAFT_NOT_FOUND"


@pytest.mark.asyncio
async def test_update_draft_another_members_draft_returns_same_not_found_response(monkeypatch):
    owner_id = uuid4()
    other_user_id = uuid4()
    draft_id = uuid4()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=owner_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=other_user_id)
    service = _service(draft_stub=stub)

    with pytest.raises(NotFoundException) as own_exc:
        await service.update_draft(uuid4(), UpdateBookingDraftCommand(lines=[]))
    with pytest.raises(NotFoundException) as other_exc:
        await service.update_draft(draft_id, UpdateBookingDraftCommand(lines=[]))

    assert own_exc.value.error_code == other_exc.value.error_code == "FACILITY_BOOKING_DRAFT_NOT_FOUND"
    assert own_exc.value.status_code == other_exc.value.status_code


@pytest.mark.asyncio
async def test_update_draft_rejects_zero_lines(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_draft(draft_id, UpdateBookingDraftCommand(lines=[]))
    assert exc_info.value.error_code == "FACILITY_BOOKING_ROOMS_REQUIRED"


@pytest.mark.asyncio
async def test_update_draft_rejects_lines_over_configured_cap(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    cap = 3
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=user_id)
    room_ids = [new_uuid() for _ in range(cap + 1)]
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 11, 0, tzinfo=timezone.utc)
    command = UpdateBookingDraftCommand(
        lines=[BookingDraftLineCommand(facility_id=room_id, start_at=start, end_at=end, sequence=idx) for idx, room_id in enumerate(room_ids)]
    )
    service = _service(draft_stub=stub, setting_stub=StubSettingService(max_booking_lines=cap))
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_draft(draft_id, command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_MAX_ROOMS"


@pytest.mark.asyncio
async def test_update_draft_rejects_lines_spanning_more_than_one_day(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    room_id = new_uuid()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=user_id)
    command = UpdateBookingDraftCommand(
        lines=[
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 1, 12, 0, tzinfo=timezone.utc),
                sequence=0,
            ),
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 2, 10, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 2, 12, 0, tzinfo=timezone.utc),
                sequence=1,
            ),
        ]
    )
    service = _service(draft_stub=stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_draft(draft_id, command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINES_NOT_SAME_DAY"


@pytest.mark.asyncio
async def test_update_draft_rejects_cross_midnight_line(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    room_id = new_uuid()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=user_id)
    command = UpdateBookingDraftCommand(
        lines=[
            BookingDraftLineCommand(
                facility_id=room_id,
                start_at=datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc),
                end_at=datetime(2026, 5, 2, 8, 0, tzinfo=timezone.utc),
                sequence=0,
            )
        ]
    )
    service = _service(draft_stub=stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.update_draft(draft_id, command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_LINE_CROSS_MIDNIGHT"


@pytest.mark.asyncio
async def test_update_draft_keeps_id_unchanged_and_replaces_lines(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    old_room_id = new_uuid()
    new_room_id = new_uuid()
    old_start = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    old_end = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=old_start.date(), lines=[_stored_line(facility_id=old_room_id, start_at=old_start, end_at=old_end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    new_start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    new_end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    command = UpdateBookingDraftCommand(lines=[BookingDraftLineCommand(facility_id=new_room_id, start_at=new_start, end_at=new_end, sequence=0)])
    service = _service(draft_stub=stub)

    result = await service.update_draft(draft_id, command)

    assert result.id == draft_id
    assert len(result.lines) == 1
    assert result.lines[0].facility_id == new_room_id
    assert len(stub.replace_lines_calls[0]) == 1
    assert stub.replace_lines_calls[0][0]["facility_id"] == new_room_id


@pytest.mark.asyncio
async def test_delete_all_my_drafts_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: None)
    service = _service()
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.delete_all_my_drafts()


@pytest.mark.asyncio
async def test_delete_all_my_drafts_removes_the_members_single_draft(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub)

    await service.delete_all_my_drafts()

    assert stub.delete_all_for_user_calls == [user_id]
    assert draft_id not in stub.draft_by_id


@pytest.mark.asyncio
async def test_delete_all_my_drafts_removes_several_drafts(monkeypatch):
    user_id = uuid4()
    draft_ids = [uuid4(), uuid4(), uuid4()]
    stub = StubBookingDraftRepository(
        draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date()) for draft_id in draft_ids}
    )
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub)

    await service.delete_all_my_drafts()

    assert stub.draft_by_id == {}


@pytest.mark.asyncio
async def test_delete_all_my_drafts_is_a_noop_when_member_has_none(monkeypatch):
    user_id = uuid4()
    stub = StubBookingDraftRepository()
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub)

    await service.delete_all_my_drafts()

    assert stub.delete_all_for_user_calls == [user_id]


@pytest.mark.asyncio
async def test_delete_all_my_drafts_never_removes_another_members_draft(monkeypatch):
    owner_id = uuid4()
    other_user_id = uuid4()
    owner_draft_id = uuid4()
    other_draft_id = uuid4()
    stub = StubBookingDraftRepository(
        draft_by_id={
            owner_draft_id: _stored_draft(draft_id=owner_draft_id, user_id=owner_id, date_=datetime(2026, 5, 1).date()),
            other_draft_id: _stored_draft(draft_id=other_draft_id, user_id=other_user_id, date_=datetime(2026, 5, 1).date()),
        }
    )
    _user_ctx(monkeypatch, user_id=owner_id)
    service = _service(draft_stub=stub)

    await service.delete_all_my_drafts()

    assert owner_draft_id not in stub.draft_by_id
    assert other_draft_id in stub.draft_by_id


@pytest.mark.asyncio
async def test_delete_all_my_drafts_leaves_confirmed_bookings_untouched(monkeypatch):
    """Bulk-delete only ever touches Booking Draft rows -- a real Booking is a separate table (ADR 0018)."""
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubBookingDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, date_=datetime(2026, 5, 1).date())})
    booking_stub = StubBookingRepository()
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub, booking_stub=booking_stub)

    await service.delete_all_my_drafts()

    assert booking_stub.cancel_calls == []
    assert booking_stub.insert_calls == []
    assert booking_stub.update_header_calls == []
    assert booking_stub.replace_rooms_calls == []
    assert booking_stub.replace_slots_calls == []


@pytest.mark.asyncio
async def test_update_draft_two_sequential_patches_last_write_wins(monkeypatch):
    """The second PATCH's content replaces the first entirely -- no error, no merge."""
    user_id = uuid4()
    draft_id = uuid4()
    room_a = new_uuid()
    room_b = new_uuid()
    room_c = new_uuid()
    start = datetime(2026, 5, 1, 9, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    stub = StubBookingDraftRepository(
        draft_by_id={
            draft_id: _stored_draft(
                draft_id=draft_id, user_id=user_id, date_=start.date(), lines=[_stored_line(facility_id=room_a, start_at=start, end_at=end)]
            )
        }
    )
    _user_ctx(monkeypatch, user_id=user_id)
    service = _service(draft_stub=stub)

    first_command = UpdateBookingDraftCommand(
        lines=[
            BookingDraftLineCommand(facility_id=room_a, start_at=start, end_at=end, sequence=0),
            BookingDraftLineCommand(facility_id=room_b, start_at=start, end_at=end, sequence=1),
        ]
    )
    await service.update_draft(draft_id, first_command)

    second_command = UpdateBookingDraftCommand(lines=[BookingDraftLineCommand(facility_id=room_c, start_at=start, end_at=end, sequence=0)])
    second_result = await service.update_draft(draft_id, second_command)

    assert len(second_result.lines) == 1
    assert second_result.lines[0].facility_id == room_c
    assert stub.draft_by_id[draft_id].lines == [BookingDraftStoredLineResult(facility_id=room_c, start_at=start, end_at=end, sequence=0)]
