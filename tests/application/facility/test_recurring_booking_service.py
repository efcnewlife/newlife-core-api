"""
RecurringBookingService create_series tests.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.commands import BookingRoomLineCommand, CreateRecurringBookingSeriesCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import RecurringBookingSeriesResult
from portal.domain.facility.constants import BookingErrorCode, BookingSlotStatus, BookingStatus, BookingType, FacilityErrorCode
from portal.domain.org.constants import MinistryStatus
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException
from tests.fixtures.facility.factories import make_ministry_detail, make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubPricingService,
    StubRecurringBookingRepository,
    StubRoomBlackoutRepository,
    StubUserReadService,
)
from tests.fixtures.system.stubs import StubSettingService

TORONTO = ZoneInfo("America/Toronto")
OPEN_WINDOW_NOW = datetime(2025, 12, 8, 17, 0, tzinfo=timezone.utc)
FIRST_TUESDAY = date(2026, 1, 6)
LAST_TUESDAY = date(2026, 1, 27)


def _user_ctx(monkeypatch, *, user_id, email="booker@efcnewlife.org"):
    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.email = email
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
    return ctx


def _command(**overrides) -> CreateRecurringBookingSeriesCommand:
    room_id = overrides.pop("facility_id", new_uuid())
    rooms = overrides.pop("rooms", [BookingRoomLineCommand(facility_id=room_id, sequence=0)])
    return CreateRecurringBookingSeriesCommand(
        first_occurrence_date=overrides.pop("first_occurrence_date", FIRST_TUESDAY),
        last_occurrence_date=overrides.pop("last_occurrence_date", LAST_TUESDAY),
        local_start_time=overrides.pop("local_start_time", time(10, 0)),
        local_end_time=overrides.pop("local_end_time", time(12, 0)),
        rooms=rooms,
        **overrides,
    )


def _service(
    monkeypatch,
    *,
    user_id=None,
    email="booker@efcnewlife.org",
    booking_stub=None,
    series_stub=None,
    ministry_stub=None,
    blackout_stub=None,
    setting_stub=None,
    user_read_stub=None,
    now_utc=None,
):
    user_id = user_id or uuid4()
    _user_ctx(monkeypatch, user_id=user_id, email=email)
    quote = make_preview_quote_result(quoted_amount=Decimal("100"))
    series_stub = series_stub or StubRecurringBookingRepository()
    booking_stub = booking_stub or StubBookingRepository()
    service = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=StubPricingService(quote),
        ministry_repository=ministry_stub or StubMinistryRepository(),
        room_blackout_repository=blackout_stub or StubRoomBlackoutRepository(),
        setting_service=setting_stub or StubSettingService(max_booking_lines=10),
        user_read_service=user_read_stub or StubUserReadService(email=email),
        now_utc=now_utc or (lambda: OPEN_WINDOW_NOW),
    )
    return service, series_stub, booking_stub, user_id


@pytest.mark.asyncio
async def test_create_personal_series_is_pending_payment_with_hold_and_total(monkeypatch):
    service, series_stub, booking_stub, user_id = _service(monkeypatch)
    result = await service.create_series(_command())

    assert isinstance(result, RecurringBookingSeriesResult)
    assert result.user_id == user_id
    assert result.status == BookingStatus.PENDING_PAYMENT.value
    assert result.occurrence_count == 4
    assert result.quoted_amount == Decimal("400")
    assert result.currency == "CAD"
    assert result.payment_hold_expires_at == OPEN_WINDOW_NOW + timedelta(hours=72)
    assert result.ministry_id is None
    assert result.is_priority is False
    assert [item.start_at.date() for item in result.occurrences] == [date(2026, 1, 6), date(2026, 1, 13), date(2026, 1, 20), date(2026, 1, 27)]
    assert result.occurrences[0].start_at == datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc)
    assert result.occurrences[0].end_at == datetime(2026, 1, 6, 17, 0, tzinfo=timezone.utc)
    assert result.occurrences[0].status == BookingStatus.PENDING_PAYMENT.value
    assert series_stub.insert_series_calls[0]["status"] == BookingStatus.PENDING_PAYMENT.value
    assert series_stub.insert_series_calls[0]["quoted_amount"] == Decimal("400")
    assert len(booking_stub.insert_calls) == 4
    assert all(row["booking_type"] == BookingType.RECURRING.value for row in booking_stub.insert_calls)
    assert all(row["status"] == BookingStatus.PENDING_PAYMENT.value for row in booking_stub.insert_calls)
    assert all(row["series_id"] == result.id for row in booking_stub.insert_calls)
    assert len(booking_stub.replace_slots_calls) == 4
    assert all(slot["status"] == BookingSlotStatus.CONFIRMED.value for slots in booking_stub.replace_slots_calls for slot in slots)


@pytest.mark.asyncio
async def test_create_series_rejects_period_that_crosses_june_july(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(first_occurrence_date=date(2026, 6, 2), last_occurrence_date=date(2026, 7, 7)))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_USE_PERIOD.value


@pytest.mark.asyncio
async def test_create_series_rejects_outside_four_week_availability_window(monkeypatch):
    closed_now = datetime(2025, 12, 29, 5, 0, tzinfo=timezone.utc)
    service, *_ = _service(monkeypatch, now_utc=lambda: closed_now)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_AVAILABILITY_WINDOW.value


@pytest.mark.asyncio
async def test_create_series_allows_calendar_month_window_after_four_weeks(monkeypatch):
    still_open = datetime(2025, 12, 30, 17, 0, tzinfo=timezone.utc)
    setting_stub = StubSettingService(max_booking_lines=10, availability_amount=1, availability_unit="months")
    service, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: still_open)
    result = await service.create_series(_command())
    assert result.occurrence_count == 4


@pytest.mark.asyncio
async def test_create_series_rejects_fewer_than_minimum_weeks(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(last_occurrence_date=date(2026, 1, 20)))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_MIN_OCCURRENCES.value


@pytest.mark.asyncio
async def test_create_series_rejects_weekday_mismatch(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(last_occurrence_date=date(2026, 1, 28)))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_WEEKDAY_MISMATCH.value


@pytest.mark.asyncio
async def test_create_series_rejects_nonexistent_dst_local_time(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(
            _command(first_occurrence_date=date(2026, 3, 8), last_occurrence_date=date(2026, 3, 29), local_start_time=time(2, 30), local_end_time=time(4, 0))
        )
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_DST_NONEXISTENT.value


@pytest.mark.asyncio
async def test_create_series_uses_earlier_offset_for_ambiguous_dst_time(monkeypatch):
    june_open = datetime(2026, 6, 8, 16, 0, tzinfo=timezone.utc)
    service, *_ = _service(monkeypatch, now_utc=lambda: june_open)
    result = await service.create_series(
        _command(first_occurrence_date=date(2026, 11, 1), last_occurrence_date=date(2026, 11, 22), local_start_time=time(1, 30), local_end_time=time(3, 0))
    )
    assert result.occurrences[0].start_at == datetime(2026, 11, 1, 5, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_create_series_rejects_weekly_rental_quota_collision(monkeypatch):
    existing = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_WEEKLY_QUOTA.value


@pytest.mark.asyncio
async def test_create_series_rejects_rental_earlier_in_same_sunday_week(monkeypatch):
    existing = datetime(2026, 1, 4, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_WEEKLY_QUOTA.value


@pytest.mark.asyncio
async def test_create_series_skips_weekly_quota_for_ministry_series(monkeypatch):
    ministry_id = new_uuid()
    user_id = uuid4()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = False
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    existing = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, series_stub, *_rest = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    result = await service.create_series(_command(ministry_id=ministry_id))
    assert result.occurrence_count == 4
    assert result.is_priority is False
    assert series_stub.insert_series_calls[0]["ministry_id"] == ministry_id


@pytest.mark.asyncio
async def test_create_priority_ministry_series_records_priority_without_override(monkeypatch):
    ministry_id = new_uuid()
    user_id = uuid4()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = True
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    service, series_stub, *_rest = _service(monkeypatch, user_id=user_id, ministry_stub=ministry_stub)
    result = await service.create_series(_command(ministry_id=ministry_id))
    assert result.is_priority is True
    assert series_stub.insert_series_calls[0]["is_priority"] is True


@pytest.mark.asyncio
async def test_create_ministry_series_rejects_non_steward(monkeypatch):
    ministry_id = new_uuid()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids=set())
    service, *_ = _service(monkeypatch, ministry_stub=ministry_stub)
    with pytest.raises(ForbiddenException, match="ministry"):
        await service.create_series(_command(ministry_id=ministry_id))


@pytest.mark.asyncio
async def test_create_series_rejects_non_church_email(monkeypatch):
    service, *_ = _service(monkeypatch, email="guest@gmail.com")
    with pytest.raises(ForbiddenException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value


@pytest.mark.asyncio
async def test_create_series_rejects_duplicate_rooms(monkeypatch):
    room_id = new_uuid()
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(
            _command(rooms=[BookingRoomLineCommand(facility_id=room_id, sequence=0), BookingRoomLineCommand(facility_id=room_id, sequence=1)])
        )
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_DUPLICATE_LINE.value


@pytest.mark.asyncio
async def test_create_series_copies_shared_time_window_to_every_room(monkeypatch):
    first_room = new_uuid()
    second_room = new_uuid()
    service, _series_stub, booking_stub, _user_id = _service(monkeypatch)
    result = await service.create_series(
        _command(rooms=[BookingRoomLineCommand(facility_id=first_room, sequence=0), BookingRoomLineCommand(facility_id=second_room, sequence=1)])
    )
    assert result.quoted_amount == Decimal("800")
    first_rooms = booking_stub.replace_rooms_calls[0]
    assert {row["facility_id"] for row in first_rooms} == {first_room, second_room}
    assert first_rooms[0]["start_at"] == first_rooms[1]["start_at"] == datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc)
    assert first_rooms[0]["end_at"] == first_rooms[1]["end_at"] == datetime(2026, 1, 6, 17, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_admin_on_behalf_create_uses_booker_identity(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    service, series_stub, booking_stub, _ = _service(
        monkeypatch, user_id=operator_id, email="operator@efcnewlife.org", user_read_stub=StubUserReadService(email="booker@efcnewlife.org")
    )
    result = await service.create_series(_command(user_id=booker_id))
    assert result.user_id == booker_id
    assert series_stub.insert_series_calls[0]["user_id"] == booker_id
    assert all(row["user_id"] == booker_id for row in booking_stub.insert_calls)


@pytest.mark.asyncio
async def test_admin_on_behalf_rejects_non_church_booker(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    service, *_ = _service(monkeypatch, user_id=operator_id, email="operator@efcnewlife.org", user_read_stub=StubUserReadService(email="guest@gmail.com"))
    with pytest.raises(ForbiddenException) as exc_info:
        await service.create_series(_command(user_id=booker_id))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value


@pytest.mark.asyncio
async def test_create_series_rejects_first_scheduling_conflict(monkeypatch):
    booking_stub = StubBookingRepository(has_overlap=True)
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value


@pytest.mark.asyncio
async def test_create_series_rejects_first_blackout(monkeypatch):
    blackout_stub = StubRoomBlackoutRepository(has_overlap=True)
    service, *_ = _service(monkeypatch, blackout_stub=blackout_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == BookingErrorCode.ROOM_BLACKOUT.value
