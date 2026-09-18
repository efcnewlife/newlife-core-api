"""
RecurringSeriesDraftService tests (core-api#198).
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.commands import BookingRoomLineCommand, CreateRecurringSeriesDraftCommand, UpdateRecurringSeriesDraftCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.recurring_series_draft_service import RecurringSeriesDraftService
from portal.application.facility.results import RecurringOccupyingBookingResult, RecurringSeriesDraftDetailResult, RecurringSeriesDraftStoredRoomResult
from portal.domain.facility.constants import BookingErrorCode, BookingStatus, FacilityErrorCode
from portal.domain.facility.recurring import localize_wall_time
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException, NotFoundException
from tests.fixtures.facility.factories import make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubOverrideLogRepository,
    StubPricingService,
    StubRecurringBookingRepository,
    StubRecurringOverrideNotifier,
    StubRecurringSeriesDraftRepository,
    StubRoomBlackoutRepository,
    StubUserReadService,
)
from tests.fixtures.system.stubs import StubSettingService

TORONTO = ZoneInfo("America/Toronto")
OPEN_WINDOW_NOW = datetime(2025, 12, 8, 17, 0, tzinfo=timezone.utc)
FIRST_TUESDAY = date(2026, 1, 6)
LAST_TUESDAY = date(2026, 1, 27)
SIX_WEEK_LAST_TUESDAY = date(2026, 2, 10)


def _occurrence_start_utc(occurrence_date: date, local_start: time = time(10, 0)) -> datetime:
    return localize_wall_time(occurrence_date, local_start, TORONTO).astimezone(timezone.utc)


def _user_ctx(monkeypatch, *, user_id=None, email="booker@efcnewlife.org"):
    user_id = user_id or uuid4()

    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.email = email
    ctx.username = email
    monkeypatch.setattr("portal.application.facility.recurring_series_draft_service.get_user_context", lambda: ctx)
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
    return user_id


def _command(**overrides) -> CreateRecurringSeriesDraftCommand:
    room_id = overrides.pop("facility_id", new_uuid())
    rooms = overrides.pop("rooms", [BookingRoomLineCommand(facility_id=room_id, sequence=0)])
    return CreateRecurringSeriesDraftCommand(
        title=overrides.pop("title", "Weekly choir"),
        first_occurrence_date=overrides.pop("first_occurrence_date", FIRST_TUESDAY),
        last_occurrence_date=overrides.pop("last_occurrence_date", LAST_TUESDAY),
        local_start_time=overrides.pop("local_start_time", time(10, 0)),
        local_end_time=overrides.pop("local_end_time", time(12, 0)),
        rooms=rooms,
        **overrides,
    )


def _stored_draft(*, draft_id, user_id, room_id, title="Weekly choir", excluded_dates=None) -> RecurringSeriesDraftDetailResult:
    return RecurringSeriesDraftDetailResult(
        id=draft_id,
        user_id=user_id,
        title=title,
        first_occurrence_date=FIRST_TUESDAY,
        last_occurrence_date=LAST_TUESDAY,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        excluded_dates=list(excluded_dates or []),
        rooms=[RecurringSeriesDraftStoredRoomResult(facility_id=room_id, sequence=0)],
    )


def _service(
    monkeypatch,
    *,
    user_id=None,
    email="booker@efcnewlife.org",
    draft_stub=None,
    booking_stub=None,
    series_stub=None,
    blackout_stub=None,
    pricing_stub=None,
    setting_stub=None,
    now_utc=None,
):
    user_id = _user_ctx(monkeypatch, user_id=user_id, email=email)
    quote = make_preview_quote_result(quoted_amount=Decimal("100"))
    series_stub = series_stub or StubRecurringBookingRepository()
    booking_stub = booking_stub or StubBookingRepository()
    draft_stub = draft_stub or StubRecurringSeriesDraftRepository()
    recurring = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=pricing_stub or StubPricingService(quote),
        ministry_repository=StubMinistryRepository(),
        room_blackout_repository=blackout_stub or StubRoomBlackoutRepository(),
        setting_service=setting_stub or StubSettingService(max_booking_lines=10),
        user_read_service=StubUserReadService(email=email),
        override_log_repository=StubOverrideLogRepository(),
        override_notifier=StubRecurringOverrideNotifier(),
        now_utc=now_utc or (lambda: OPEN_WINDOW_NOW),
    )
    service = RecurringSeriesDraftService(draft_stub, recurring)
    return service, draft_stub, series_stub, booking_stub, user_id


@pytest.mark.asyncio
async def test_create_draft_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.recurring_series_draft_service.get_user_context", lambda: None)
    service = RecurringSeriesDraftService(
        StubRecurringSeriesDraftRepository(),
        RecurringBookingService(
            series_repository=StubRecurringBookingRepository(),
            booking_repository=StubBookingRepository(),
            pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
            ministry_repository=StubMinistryRepository(),
            room_blackout_repository=StubRoomBlackoutRepository(),
            setting_service=StubSettingService(max_booking_lines=10),
            user_read_service=StubUserReadService(),
            override_log_repository=StubOverrideLogRepository(),
            now_utc=lambda: OPEN_WINDOW_NOW,
        ),
    )
    with pytest.raises(ForbiddenException, match="Authenticated user required"):
        await service.create_draft(_command())


@pytest.mark.asyncio
async def test_create_draft_rejects_zero_rooms(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_draft(_command(rooms=[]))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_ROOMS_REQUIRED.value


@pytest.mark.asyncio
async def test_create_draft_returns_id_and_persists_weekly_proposal(monkeypatch):
    service, draft_stub, _, _, user_id = _service(monkeypatch)
    room_id = new_uuid()
    result = await service.create_draft(_command(title="Choir rehearsal", facility_id=room_id))

    assert result.id is not None
    stored = draft_stub.insert_draft_calls[0]
    assert stored["user_id"] == user_id
    assert stored["title"] == "Choir rehearsal"
    assert stored["ministry_id"] is None
    assert stored["first_occurrence_date"] == FIRST_TUESDAY
    assert stored["last_occurrence_date"] == LAST_TUESDAY
    assert stored["local_start_time"] == time(10, 0)
    assert stored["local_end_time"] == time(12, 0)
    assert stored["excluded_dates"] == []
    assert draft_stub.insert_room_calls[0][0]["facility_id"] == room_id


@pytest.mark.asyncio
async def test_create_draft_allows_missing_title(monkeypatch):
    service, draft_stub, *_ = _service(monkeypatch)
    result = await service.create_draft(_command(title=None))
    assert result.id is not None
    assert draft_stub.insert_draft_calls[0]["title"] is None


@pytest.mark.asyncio
async def test_get_draft_nonexistent_id_not_found(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(NotFoundException) as exc_info:
        await service.get_draft(uuid4())
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value


@pytest.mark.asyncio
async def test_get_draft_another_members_draft_returns_same_not_found_response(monkeypatch):
    owner_id = uuid4()
    other_user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=owner_id, room_id=new_uuid())})
    service, *_ = _service(monkeypatch, user_id=other_user_id, draft_stub=stub)

    with pytest.raises(NotFoundException) as own_exc:
        await service.get_draft(uuid4())
    with pytest.raises(NotFoundException) as other_exc:
        await service.get_draft(draft_id)

    assert own_exc.value.error_code == other_exc.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value
    assert own_exc.value.status_code == other_exc.value.status_code


@pytest.mark.asyncio
async def test_get_draft_returns_live_quote_conflicts_and_payment_hold(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=room_id)})
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    result = await service.get_draft(draft_id)

    assert result.id == draft_id
    assert result.title == "Weekly choir"
    assert result.rooms[0].facility_id == room_id
    assert result.quoted_amount == Decimal("400")
    assert result.occurrence_count == 4
    assert result.is_confirmable is True
    assert result.pending_payment_hold_hours == 72
    assert result.payment_hold_expires_at == OPEN_WINDOW_NOW + timedelta(hours=72)
    assert result.conflicts == []


@pytest.mark.asyncio
async def test_get_draft_quote_is_not_a_cached_creation_time_snapshot(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid())})
    pricing_stub = StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100")))
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub, pricing_stub=pricing_stub)

    first = await service.get_draft(draft_id)
    pricing_stub.quote_result = make_preview_quote_result(quoted_amount=Decimal("250"))
    second = await service.get_draft(draft_id)

    assert first.quoted_amount == Decimal("400")
    assert second.quoted_amount == Decimal("1000")


@pytest.mark.asyncio
async def test_get_draft_invalid_exclusion_is_not_confirmable(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(
        draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid(), excluded_dates=[FIRST_TUESDAY])}
    )
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    result = await service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert result.invalidity_code == FacilityErrorCode.RECURRING_INVALID_EXCLUSION.value
    assert result.excluded_dates == [FIRST_TUESDAY]


@pytest.mark.asyncio
async def test_get_draft_without_title_is_not_confirmable(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid(), title=None)})
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    result = await service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert result.invalidity_code == FacilityErrorCode.BOOKING_TITLE_INVALID.value
    assert result.quoted_amount == Decimal("400")


@pytest.mark.asyncio
async def test_get_draft_stale_occupancy_is_not_confirmable(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = _occurrence_start_utc(FIRST_TUESDAY)
    occupying = RecurringOccupyingBookingResult(
        booking_id=uuid4(), user_id=uuid4(), ministry_id=None, facility_ids=[room_id], start_at=start, end_at=start + timedelta(hours=2)
    )
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=room_id)})
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub, booking_stub=StubBookingRepository(occupying_bookings=[occupying]))

    result = await service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert result.conflicts[0].occurrence_date == FIRST_TUESDAY
    assert result.invalidity_code == BookingErrorCode.SCHEDULING_CONFLICT.value


@pytest.mark.asyncio
async def test_update_draft_keeps_id_and_replaces_proposal(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    old_room = new_uuid()
    new_room = new_uuid()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=old_room)})
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    result = await service.update_draft(
        draft_id,
        UpdateRecurringSeriesDraftCommand(
            title="Revised choir",
            first_occurrence_date=FIRST_TUESDAY,
            last_occurrence_date=SIX_WEEK_LAST_TUESDAY,
            local_start_time=time(14, 0),
            local_end_time=time(16, 0),
            rooms=[BookingRoomLineCommand(facility_id=new_room, sequence=0)],
        ),
    )

    assert result.id == draft_id
    assert result.title == "Revised choir"
    assert result.last_occurrence_date == SIX_WEEK_LAST_TUESDAY
    assert result.local_start_time == time(14, 0)
    assert result.rooms[0].facility_id == new_room


@pytest.mark.asyncio
async def test_update_draft_another_members_draft_returns_same_not_found_response(monkeypatch):
    owner_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=owner_id, room_id=new_uuid())})
    service, *_ = _service(monkeypatch, user_id=uuid4(), draft_stub=stub)

    with pytest.raises(NotFoundException) as exc_info:
        await service.update_draft(draft_id, _command())
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value


@pytest.mark.asyncio
async def test_confirm_draft_creates_one_pending_payment_series_and_consumes_draft(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid())})
    service, _, series_stub, booking_stub, _ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    result = await service.confirm_draft(draft_id)

    assert result.status == BookingStatus.PENDING_PAYMENT.value
    assert result.occurrence_count == 4
    assert result.quoted_amount == Decimal("400")
    assert len(series_stub.insert_series_calls) == 1
    assert len(booking_stub.insert_calls) == 4
    assert draft_id not in stub.draft_by_id
    assert stub.delete_draft_calls == [draft_id]


@pytest.mark.asyncio
async def test_confirm_stale_draft_does_not_create_a_series(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    draft_id = uuid4()
    start = _occurrence_start_utc(FIRST_TUESDAY)
    occupying = RecurringOccupyingBookingResult(
        booking_id=uuid4(), user_id=uuid4(), ministry_id=None, facility_ids=[room_id], start_at=start, end_at=start + timedelta(hours=2)
    )
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=room_id)})
    service, _, series_stub, booking_stub, _ = _service(
        monkeypatch, user_id=user_id, draft_stub=stub, booking_stub=StubBookingRepository(occupying_bookings=[occupying])
    )

    with pytest.raises(ConflictErrorException) as exc_info:
        await service.confirm_draft(draft_id)

    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_CONFIRMABLE.value
    assert exc_info.value.context["invalidity_code"] == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert series_stub.insert_series_calls == []
    assert booking_stub.insert_calls == []
    assert draft_id in stub.draft_by_id


@pytest.mark.asyncio
async def test_confirm_missing_draft_does_not_create_a_series(monkeypatch):
    service, _, series_stub, *_ = _service(monkeypatch)
    with pytest.raises(NotFoundException) as exc_info:
        await service.confirm_draft(uuid4())
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value
    assert series_stub.insert_series_calls == []


@pytest.mark.asyncio
async def test_confirm_another_members_draft_does_not_create_a_series(monkeypatch):
    owner_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=owner_id, room_id=new_uuid())})
    service, _, series_stub, *_ = _service(monkeypatch, user_id=uuid4(), draft_stub=stub)

    with pytest.raises(NotFoundException) as exc_info:
        await service.confirm_draft(draft_id)

    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_DRAFT_NOT_FOUND.value
    assert series_stub.insert_series_calls == []


@pytest.mark.asyncio
async def test_confirm_consumed_draft_does_not_create_a_second_series(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid())})
    service, _, series_stub, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    await service.confirm_draft(draft_id)
    with pytest.raises(NotFoundException):
        await service.confirm_draft(draft_id)

    assert len(series_stub.insert_series_calls) == 1


@pytest.mark.asyncio
async def test_confirm_untitled_draft_does_not_create_a_series(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid(), title=None)})
    service, _, series_stub, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub)

    with pytest.raises(ConflictErrorException) as exc_info:
        await service.confirm_draft(draft_id)

    assert exc_info.value.context["invalidity_code"] == FacilityErrorCode.BOOKING_TITLE_INVALID.value
    assert series_stub.insert_series_calls == []


@pytest.mark.asyncio
async def test_delete_all_my_drafts_removes_owned_drafts_only(monkeypatch):
    owner_id = uuid4()
    other_user_id = uuid4()
    owner_draft_id = uuid4()
    other_draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(
        draft_by_id={
            owner_draft_id: _stored_draft(draft_id=owner_draft_id, user_id=owner_id, room_id=new_uuid()),
            other_draft_id: _stored_draft(draft_id=other_draft_id, user_id=other_user_id, room_id=new_uuid()),
        }
    )
    service, *_ = _service(monkeypatch, user_id=owner_id, draft_stub=stub)

    await service.delete_all_my_drafts()

    assert owner_draft_id not in stub.draft_by_id
    assert other_draft_id in stub.draft_by_id


@pytest.mark.asyncio
async def test_delete_all_my_drafts_never_deletes_a_created_series(monkeypatch):
    user_id = uuid4()
    draft_id = uuid4()
    stub = StubRecurringSeriesDraftRepository(draft_by_id={draft_id: _stored_draft(draft_id=draft_id, user_id=user_id, room_id=new_uuid())})
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    service, *_ = _service(monkeypatch, user_id=user_id, draft_stub=stub, series_stub=series_stub, booking_stub=booking_stub)

    await service.confirm_draft(draft_id)
    await service.create_draft(_command())
    await service.delete_all_my_drafts()

    assert series_stub.insert_series_calls
    assert series_stub.update_series_calls == []
    assert booking_stub.cancel_calls == []
    assert stub.draft_by_id == {}
