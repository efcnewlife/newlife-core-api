"""
RecurringBookingService create_series tests.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.commands import BookingRoomLineCommand, CreateRecurringBookingSeriesCommand
from portal.application.facility.discount_eligibility_service import DiscountEligibilityService
from portal.application.facility.pricing_service import PricingService
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import RecurringBookingPreviewResult, RecurringBookingSeriesResult, RecurringOccupyingBookingResult
from portal.application.org.results import MinistryMemberResult
from portal.config import settings
from portal.domain.facility.constants import (
    BookingErrorCode,
    BookingSlotStatus,
    BookingStatus,
    BookingType,
    FacilityErrorCode,
    RecurringConflictKind,
    RentalDiscountCode,
)
from portal.domain.facility.recurring import localize_wall_time
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import BadRequestException, ConflictErrorException, ForbiddenException
from tests.fixtures.facility.factories import make_discount_rule, make_hourly_and_daily_rates, make_ministry_detail, make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubOverrideLogRepository,
    StubPricingService,
    StubRecurringBookingRepository,
    StubRecurringOverrideNotifier,
    StubRentalRepository,
    StubRoomBlackoutRepository,
    StubRoomRepository,
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
        title=overrides.pop("title", "Weekly choir"),
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
    override_log_stub=None,
    override_notifier=None,
    now_utc=None,
):
    user_id = user_id or uuid4()
    _user_ctx(monkeypatch, user_id=user_id, email=email)
    quote = make_preview_quote_result(quoted_amount=Decimal("100"))
    series_stub = series_stub or StubRecurringBookingRepository()
    booking_stub = booking_stub or StubBookingRepository()
    override_log_stub = override_log_stub or StubOverrideLogRepository()
    override_notifier = override_notifier or StubRecurringOverrideNotifier()
    service = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=StubPricingService(quote),
        ministry_repository=ministry_stub or StubMinistryRepository(),
        room_blackout_repository=blackout_stub or StubRoomBlackoutRepository(),
        setting_service=setting_stub or StubSettingService(max_booking_lines=10),
        user_read_service=user_read_stub or StubUserReadService(email=email),
        override_log_repository=override_log_stub,
        override_notifier=override_notifier,
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
    assert result.payment_hold_expires_at == datetime(2025, 12, 12, 5, 0, tzinfo=timezone.utc)
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
async def test_get_window_status_is_open_during_december_window(monkeypatch):
    service, *_ = _service(monkeypatch)
    result = await service.get_window_status()
    assert result.is_open is True
    assert result.next_opening_date is None
    jan_jun = await service.get_window_status(date(2026, 1, 6))
    assert jan_jun.is_open is True
    jul_dec = await service.get_window_status(date(2026, 7, 7))
    assert jul_dec.is_open is False
    assert jul_dec.next_opening_date == date(2026, 6, 1)


@pytest.mark.asyncio
async def test_get_window_status_is_closed_in_september(monkeypatch):
    closed_now = datetime(2026, 9, 17, 16, 0, tzinfo=timezone.utc)
    service, *_ = _service(monkeypatch, now_utc=lambda: closed_now)
    result = await service.get_window_status()
    assert result.is_open is False
    assert result.next_opening_date == date(2026, 12, 1)


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


CLOSED_NOW = datetime(2025, 12, 29, 5, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_get_window_status_reflects_test_window_override_when_non_prod(monkeypatch):
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: CLOSED_NOW)
    result = await service.get_window_status()
    assert result.is_open is True
    assert result.next_opening_date is None


@pytest.mark.asyncio
async def test_get_window_status_ignores_test_window_override_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "prod")
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: CLOSED_NOW)
    result = await service.get_window_status()
    assert result.is_open is False
    assert result.next_opening_date == date(2026, 6, 1)


@pytest.mark.asyncio
async def test_create_series_succeeds_outside_window_when_test_override_enabled_non_prod(monkeypatch):
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: CLOSED_NOW)
    result = await service.create_series(_command())
    assert result.occurrence_count == 4


@pytest.mark.asyncio
async def test_create_series_rejects_outside_window_when_test_override_enabled_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "prod")
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: CLOSED_NOW)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_AVAILABILITY_WINDOW.value


@pytest.mark.asyncio
async def test_create_series_allows_allowlisted_exact_email_non_church_booker(monkeypatch):
    setting_stub = StubSettingService(max_booking_lines=10, test_booker_email_addresses=["qa1@test.local"])
    service, *_ = _service(monkeypatch, email="qa1@test.local", setting_stub=setting_stub)
    result = await service.create_series(_command())
    assert result.occurrence_count == 4


@pytest.mark.asyncio
async def test_create_series_allows_allowlisted_domain_suffix_non_church_booker(monkeypatch):
    setting_stub = StubSettingService(max_booking_lines=10, test_booker_email_suffixes=["@qa.test.local"])
    service, *_ = _service(monkeypatch, email="anyone@qa.test.local", setting_stub=setting_stub)
    result = await service.create_series(_command())
    assert result.occurrence_count == 4


@pytest.mark.asyncio
async def test_create_series_rejects_unlisted_non_church_booker_even_with_allowlist_populated(monkeypatch):
    setting_stub = StubSettingService(max_booking_lines=10, test_booker_email_addresses=["qa1@test.local"])
    service, *_ = _service(monkeypatch, email="guest@gmail.com", setting_stub=setting_stub)
    with pytest.raises(ForbiddenException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value


@pytest.mark.asyncio
async def test_create_series_ignores_test_booker_allowlist_in_production(monkeypatch):
    monkeypatch.setattr(settings, "ENV", "prod")
    setting_stub = StubSettingService(max_booking_lines=10, test_booker_email_addresses=["qa1@test.local"])
    service, *_ = _service(monkeypatch, email="qa1@test.local", setting_stub=setting_stub)
    with pytest.raises(ForbiddenException) as exc_info:
        await service.create_series(_command())
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_NOT_ELIGIBLE.value


@pytest.mark.asyncio
async def test_admin_on_behalf_allows_allowlisted_booker_via_repository_lookup(monkeypatch):
    operator_id = uuid4()
    booker_id = uuid4()
    setting_stub = StubSettingService(max_booking_lines=10, test_booker_email_addresses=["qa1@test.local"])
    service, *_ = _service(
        monkeypatch, user_id=operator_id, email="operator@efcnewlife.org", setting_stub=setting_stub, user_read_stub=StubUserReadService(email="qa1@test.local")
    )
    result = await service.create_series(_command(user_id=booker_id))
    assert result.user_id == booker_id


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


@pytest.mark.asyncio
async def test_preview_lists_occupancy_conflicts_per_occurrence(monkeypatch):
    room_id = new_uuid()
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, occupied)})
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    result = await service.preview_conflicts(_command(facility_id=room_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert isinstance(result, RecurringBookingPreviewResult)
    assert [(item.occurrence_date, item.kind, item.facility_ids) for item in result.conflicts] == [
        (date(2026, 1, 13), RecurringConflictKind.OCCUPANCY.value, [room_id])
    ]


@pytest.mark.asyncio
async def test_preview_lists_blackout_conflicts_per_occurrence(monkeypatch):
    room_id = new_uuid()
    closed = _occurrence_start_utc(date(2026, 1, 20))
    blackout_stub = StubRoomBlackoutRepository(overlapping_blackouts={(room_id, closed)})
    service, *_ = _service(monkeypatch, blackout_stub=blackout_stub)
    result = await service.preview_conflicts(_command(facility_id=room_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert [(item.occurrence_date, item.kind, item.facility_ids) for item in result.conflicts] == [
        (date(2026, 1, 20), RecurringConflictKind.BLACKOUT.value, [room_id])
    ]


@pytest.mark.asyncio
async def test_preview_lists_weekly_quota_conflicts_per_occurrence(monkeypatch):
    existing = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    result = await service.preview_conflicts(_command(last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert [(item.occurrence_date, item.kind, item.facility_ids) for item in result.conflicts] == [
        (date(2026, 1, 6), RecurringConflictKind.WEEKLY_QUOTA.value, [])
    ]


@pytest.mark.asyncio
async def test_preview_omits_weekly_quota_for_ministry_series(monkeypatch):
    ministry_id = new_uuid()
    user_id = uuid4()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = False
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    existing = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    result = await service.preview_conflicts(_command(ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))
    assert result.conflicts == []


@pytest.mark.asyncio
async def test_create_series_excludes_previewed_dates_and_recalculates_total(monkeypatch):
    room_id = new_uuid()
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    closed = _occurrence_start_utc(date(2026, 1, 20))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, occupied)})
    blackout_stub = StubRoomBlackoutRepository(overlapping_blackouts={(room_id, closed)})
    service, series_stub, *_rest = _service(monkeypatch, booking_stub=booking_stub, blackout_stub=blackout_stub)
    result = await service.create_series(
        _command(facility_id=room_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY, excluded_dates=[date(2026, 1, 13), date(2026, 1, 20)])
    )

    assert result.occurrence_count == 4
    assert result.quoted_amount == Decimal("400")
    assert [item.start_at.date() for item in result.occurrences] == [date(2026, 1, 6), date(2026, 1, 27), date(2026, 2, 3), date(2026, 2, 10)]
    assert series_stub.insert_series_calls[0]["quoted_amount"] == Decimal("400")
    assert len(booking_stub.insert_calls) == 4


@pytest.mark.asyncio
async def test_create_series_rejects_arbitrary_exclusion_of_a_free_date(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(excluded_dates=[date(2026, 1, 13)]))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_INVALID_EXCLUSION.value


@pytest.mark.asyncio
async def test_create_series_rejects_exclusion_outside_generated_dates(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(excluded_dates=[date(2026, 1, 7)]))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_INVALID_EXCLUSION.value


@pytest.mark.asyncio
async def test_create_series_rejects_exclusions_that_drop_below_minimum_weeks(monkeypatch):
    room_id = new_uuid()
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, occupied)})
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(facility_id=room_id, excluded_dates=[date(2026, 1, 13)]))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_MIN_OCCURRENCES.value


@pytest.mark.asyncio
async def test_create_series_rejects_stale_preview_when_remaining_date_conflicts(monkeypatch):
    room_id = new_uuid()
    preview_occupied = _occurrence_start_utc(date(2026, 1, 13))
    stale_occupied = _occurrence_start_utc(date(2026, 1, 27))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, preview_occupied), (room_id, stale_occupied)})
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_series(_command(facility_id=room_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY, excluded_dates=[date(2026, 1, 13)]))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value


@pytest.mark.asyncio
async def test_create_series_rejects_stale_preview_when_remaining_date_is_blackout(monkeypatch):
    room_id = new_uuid()
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    closed = _occurrence_start_utc(date(2026, 1, 27))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, occupied)})
    blackout_stub = StubRoomBlackoutRepository(overlapping_blackouts={(room_id, closed)})
    service, *_ = _service(monkeypatch, booking_stub=booking_stub, blackout_stub=blackout_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(facility_id=room_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY, excluded_dates=[date(2026, 1, 13)]))
    assert exc_info.value.error_code == BookingErrorCode.ROOM_BLACKOUT.value


@pytest.mark.asyncio
async def test_create_series_succeeds_after_revising_conflicting_room(monkeypatch):
    occupied_room = new_uuid()
    free_room = new_uuid()
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(overlapping_slots={(occupied_room, occupied)})
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    result = await service.create_series(_command(facility_id=free_room))
    assert result.occurrence_count == 4
    assert result.occurrences[0].facility_ids == [free_room]


@pytest.mark.asyncio
async def test_create_non_priority_ministry_series_can_exclude_occupancy(monkeypatch):
    ministry_id = new_uuid()
    user_id = uuid4()
    room_id = new_uuid()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = False
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    occupied = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(overlapping_slots={(room_id, occupied)})
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    result = await service.create_series(
        _command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY, excluded_dates=[date(2026, 1, 13)])
    )
    assert result.occurrence_count == 5
    assert result.ministry_id == ministry_id
    assert date(2026, 1, 13) not in [item.start_at.date() for item in result.occurrences]


@pytest.mark.asyncio
async def test_create_series_can_exclude_weekly_quota_conflict(monkeypatch):
    existing = datetime(2026, 1, 8, 15, 0, tzinfo=timezone.utc)
    booking_stub = StubBookingRepository(rental_starts=[existing])
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)
    result = await service.create_series(_command(last_occurrence_date=SIX_WEEK_LAST_TUESDAY, excluded_dates=[date(2026, 1, 6)]))
    assert result.occurrence_count == 5
    assert date(2026, 1, 6) not in [item.start_at.date() for item in result.occurrences]


def _priority_ministry(*, user_id, ministry_id=None, members=None):
    ministry_id = ministry_id or new_uuid()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = True
    ministry.name = "Choir"
    return ministry_id, StubMinistryRepository(
        ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id}, members_by_ministry={ministry_id: members or []}
    )


def _occupying_rental(*, facility_id, occurrence_date, booking_id=None, user_id=None, start_at=None):
    start_at = start_at or _occurrence_start_utc(occurrence_date)
    return RecurringOccupyingBookingResult(
        booking_id=booking_id or new_uuid(),
        user_id=user_id or uuid4(),
        ministry_id=None,
        facility_ids=[facility_id],
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
    )


@pytest.mark.asyncio
async def test_preview_ministry_conflict_includes_primary_steward_contact(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    other_ministry_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    occupying_start = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(
        occupying_bookings=[
            RecurringOccupyingBookingResult(
                booking_id=new_uuid(),
                user_id=uuid4(),
                ministry_id=other_ministry_id,
                facility_ids=[room_id],
                start_at=occupying_start,
                end_at=occupying_start + timedelta(hours=2),
            )
        ]
    )
    ministry_stub.members_by_ministry[other_ministry_id] = [
        MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat Steward", email="pat.steward@efcnewlife.org")
    ]
    other_ministry = make_ministry_detail(other_ministry_id)
    other_ministry.status = MinistryStatus.ACTIVE.value
    ministry_stub.ministry_by_id[other_ministry_id] = other_ministry
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)

    result = await service.preview_conflicts(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert [(item.occurrence_date, item.kind, item.facility_ids) for item in result.conflicts] == [
        (date(2026, 1, 13), RecurringConflictKind.MINISTRY.value, [room_id])
    ]
    conflict = result.conflicts[0]
    assert conflict.is_overridable is False
    assert conflict.ministry_id == other_ministry_id
    assert conflict.ministry_steward_display_name == "Pat Steward"
    assert conflict.ministry_steward_email == "pat.steward@efcnewlife.org"


@pytest.mark.asyncio
async def test_priority_preview_marks_future_rental_occupancy_overridable(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    rental = _occupying_rental(facility_id=room_id, occurrence_date=date(2026, 1, 13))
    booking_stub = StubBookingRepository(occupying_bookings=[rental])
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)

    result = await service.preview_conflicts(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert result.conflicts[0].kind == RecurringConflictKind.OCCUPANCY.value
    assert result.conflicts[0].is_overridable is True
    assert result.conflicts[0].occurrence_date == date(2026, 1, 13)


@pytest.mark.asyncio
async def test_priority_create_overrides_future_rental_and_writes_audit(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    rental_booker_id = uuid4()
    rental_booking_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    rental = _occupying_rental(facility_id=room_id, occurrence_date=date(2026, 1, 13), booking_id=rental_booking_id, user_id=rental_booker_id)
    booking_stub = StubBookingRepository(occupying_bookings=[rental])
    override_log_stub = StubOverrideLogRepository()
    notifier = StubRecurringOverrideNotifier()
    service, series_stub, *_rest = _service(
        monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub, override_log_stub=override_log_stub, override_notifier=notifier
    )

    result = await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))

    assert result.occurrence_count == 6
    assert result.is_priority is True
    assert booking_stub.override_calls == [dict(booking_id=rental_booking_id, overridden_by_id=user_id, reason="Priority Ministry override")]
    assert len(override_log_stub.insert_calls) == 1
    log_row = override_log_stub.insert_calls[0][0]
    assert log_row["overridden_booking_id"] == rental_booking_id
    assert log_row["overridden_by_id"] == user_id
    assert log_row["facility_id"] == room_id
    assert log_row["outcome"] == "override_applied"
    new_occurrence_ids = {item.id for item in result.occurrences}
    assert log_row["facility_booking_id"] in new_occurrence_ids
    assert len(notifier.calls) == 1
    assert notifier.calls[0].affected_booker_ids == [rental_booker_id]
    assert notifier.calls[0].church_activity_name == "Choir"


@pytest.mark.asyncio
async def test_priority_create_rejects_blackout_instead_of_overriding(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    closed = _occurrence_start_utc(date(2026, 1, 20))
    blackout_stub = StubRoomBlackoutRepository(overlapping_blackouts={(room_id, closed)})
    service, *_ = _service(monkeypatch, user_id=user_id, ministry_stub=ministry_stub, blackout_stub=blackout_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id))
    assert exc_info.value.error_code == BookingErrorCode.ROOM_BLACKOUT.value


@pytest.mark.asyncio
async def test_priority_create_rejects_ministry_occupancy_with_steward_context(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    other_ministry_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    occupying_start = _occurrence_start_utc(date(2026, 1, 13))
    booking_stub = StubBookingRepository(
        occupying_bookings=[
            RecurringOccupyingBookingResult(
                booking_id=new_uuid(),
                user_id=uuid4(),
                ministry_id=other_ministry_id,
                facility_ids=[room_id],
                start_at=occupying_start,
                end_at=occupying_start + timedelta(hours=2),
            )
        ]
    )
    ministry_stub.members_by_ministry[other_ministry_id] = [
        MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat Steward", email="pat.steward@efcnewlife.org")
    ]
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_MINISTRY_CONFLICT.value
    assert exc_info.value.context["ministry_steward_display_name"] == "Pat Steward"
    assert exc_info.value.context["ministry_steward_email"] == "pat.steward@efcnewlife.org"


@pytest.mark.asyncio
async def test_non_priority_ministry_cannot_override_rental_occupancy(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry_id = new_uuid()
    ministry = make_ministry_detail(ministry_id)
    ministry.status = MinistryStatus.ACTIVE.value
    ministry.has_priority_booking = False
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry_id: ministry}, booking_member_user_ids={user_id})
    rental = _occupying_rental(facility_id=room_id, occurrence_date=date(2026, 1, 13))
    booking_stub = StubBookingRepository(occupying_bookings=[rental])
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert booking_stub.override_calls == []


@pytest.mark.asyncio
async def test_priority_create_does_not_override_past_rental_occupancy(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    first_tuesday_start = _occurrence_start_utc(FIRST_TUESDAY)
    booking_stub = StubBookingRepository(
        occupying_bookings=[
            RecurringOccupyingBookingResult(
                booking_id=new_uuid(),
                user_id=uuid4(),
                ministry_id=None,
                facility_ids=[room_id],
                start_at=datetime(2025, 11, 1, 15, 0, tzinfo=timezone.utc),
                end_at=first_tuesday_start + timedelta(hours=2),
            )
        ]
    )
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub)
    with pytest.raises(ConflictErrorException) as exc_info:
        await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert booking_stub.override_calls == []


@pytest.mark.asyncio
async def test_priority_override_mail_failure_does_not_block_create(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry_id, ministry_stub = _priority_ministry(user_id=user_id)
    rental = _occupying_rental(facility_id=room_id, occurrence_date=date(2026, 1, 13))
    booking_stub = StubBookingRepository(occupying_bookings=[rental])
    notifier = StubRecurringOverrideNotifier(raise_error=RuntimeError("graph down"))
    service, *_ = _service(monkeypatch, user_id=user_id, booking_stub=booking_stub, ministry_stub=ministry_stub, override_notifier=notifier)
    result = await service.create_series(_command(facility_id=room_id, ministry_id=ministry_id, last_occurrence_date=SIX_WEEK_LAST_TUESDAY))
    assert result.occurrence_count == 6
    assert len(notifier.calls) == 1


def _real_pricing_for_room(room_id, ministry_stub):
    rental = StubRentalRepository(
        rates_by_facility={room_id: make_hourly_and_daily_rates(room_id)},
        discount_rules=[
            make_discount_rule(RentalDiscountCode.MISSION_ALIGNED.value, Decimal("30")),
            make_discount_rule(RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value, Decimal("20")),
        ],
    )
    return PricingService(rental, StubRoomRepository(existing_ids={room_id}), DiscountEligibilityService(rental, ministry_stub))


@pytest.mark.asyncio
async def test_create_series_without_ministry_applies_recurring_discount(monkeypatch):
    room_id = new_uuid()
    ministry_stub = StubMinistryRepository()
    service, series_stub, booking_stub, *_ = _service(monkeypatch, ministry_stub=ministry_stub)
    service._pricing_service = _real_pricing_for_room(room_id, ministry_stub)
    result = await service.create_series(_command(facility_id=room_id))
    assert result.quoted_amount == Decimal("64.00")
    assert series_stub.insert_series_calls[0]["discount_percent"] == Decimal("20")
    assert series_stub.insert_series_calls[0]["quoted_amount"] == Decimal("64.00")
    assert series_stub.insert_series_calls[0]["is_mission_aligned"] is False
    assert all(row["discount_percent"] == Decimal("20") for row in booking_stub.insert_calls)


@pytest.mark.asyncio
async def test_create_series_qualifying_ministry_applies_thirty_percent_not_recurring(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry = make_ministry_detail()
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={user_id})
    service, series_stub, *_ = _service(monkeypatch, user_id=user_id, ministry_stub=ministry_stub)
    service._pricing_service = _real_pricing_for_room(room_id, ministry_stub)
    await service.create_series(_command(facility_id=room_id, ministry_id=ministry.id))
    payload = series_stub.insert_series_calls[0]
    assert payload["discount_percent"] == Decimal("30")
    assert payload["quoted_amount"] == Decimal("56.00")
    assert payload["is_mission_aligned"] is True


@pytest.mark.asyncio
async def test_evaluate_proposal_resolves_discount_independently_of_create(monkeypatch):
    room_id = new_uuid()
    ministry_stub = StubMinistryRepository()
    service, *_ = _service(monkeypatch, ministry_stub=ministry_stub)
    service._pricing_service = _real_pricing_for_room(room_id, ministry_stub)
    evaluation = await service.evaluate_proposal(_command(facility_id=room_id))
    assert evaluation.discount_percent == Decimal("20")
    assert evaluation.quoted_amount == Decimal("64.00")
    assert evaluation.discount_code == RentalDiscountCode.RECURRING_WEEKLY_MONTHLY.value


@pytest.mark.asyncio
async def test_evaluate_proposal_qualifying_ministry_applies_thirty_percent_not_recurring(monkeypatch):
    user_id = uuid4()
    room_id = new_uuid()
    ministry = make_ministry_detail()
    ministry_stub = StubMinistryRepository(ministry_by_id={ministry.id: ministry}, booking_member_user_ids={user_id})
    service, *_ = _service(monkeypatch, user_id=user_id, ministry_stub=ministry_stub)
    service._pricing_service = _real_pricing_for_room(room_id, ministry_stub)
    evaluation = await service.evaluate_proposal(_command(facility_id=room_id, ministry_id=ministry.id))
    assert evaluation.discount_percent == Decimal("30")
    assert evaluation.quoted_amount == Decimal("56.00")
    assert evaluation.discount_code == RentalDiscountCode.MISSION_ALIGNED.value


@pytest.mark.asyncio
async def test_evaluate_proposal_uses_pre_noon_calendar_day_deadline(monkeypatch):
    pre_noon = datetime(2025, 12, 8, 16, 59, tzinfo=timezone.utc)
    service, *_ = _service(monkeypatch, now_utc=lambda: pre_noon)
    evaluation = await service.evaluate_proposal(_command())
    assert evaluation.pending_payment_hold_days == 3
    assert evaluation.payment_hold_expires_at == datetime(2025, 12, 11, 17, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_create_series_uses_noon_cutoff_as_following_midnight(monkeypatch):
    service, series_stub, *_ = _service(monkeypatch)
    result = await service.create_series(_command())
    expires_at = datetime(2025, 12, 12, 5, 0, tzinfo=timezone.utc)
    assert result.payment_hold_expires_at == expires_at
    assert series_stub.insert_series_calls[0]["payment_hold_expires_at"] == expires_at


@pytest.mark.asyncio
async def test_create_series_post_noon_deadline_matches_proposal(monkeypatch):
    post_noon = datetime(2025, 12, 8, 17, 1, tzinfo=timezone.utc)
    service, series_stub, *_ = _service(monkeypatch, now_utc=lambda: post_noon)
    command = _command()
    evaluation = await service.evaluate_proposal(command)
    result = await service.create_series(command)
    expires_at = datetime(2025, 12, 12, 5, 0, tzinfo=timezone.utc)
    assert evaluation.payment_hold_expires_at == expires_at
    assert result.payment_hold_expires_at == expires_at
    assert series_stub.insert_series_calls[0]["payment_hold_expires_at"] == expires_at


@pytest.mark.asyncio
async def test_create_series_deadline_follows_dst_spring_forward_local_cutoff(monkeypatch):
    spring_morning = datetime(2026, 3, 8, 15, 0, tzinfo=timezone.utc)
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, series_stub, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: spring_morning)
    result = await service.create_series(_command())
    expires_at = datetime(2026, 3, 11, 16, 0, tzinfo=timezone.utc)
    assert result.payment_hold_expires_at == expires_at
    assert series_stub.insert_series_calls[0]["payment_hold_expires_at"] == expires_at


@pytest.mark.asyncio
async def test_create_series_deadline_follows_dst_fall_back_local_cutoff(monkeypatch):
    fall_morning = datetime(2026, 10, 29, 15, 0, tzinfo=timezone.utc)
    setting_stub = StubSettingService(max_booking_lines=10, test_window_override=True)
    service, series_stub, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: fall_morning)
    result = await service.create_series(_command())
    expires_at = datetime(2026, 11, 1, 17, 0, tzinfo=timezone.utc)
    assert result.payment_hold_expires_at == expires_at
    assert series_stub.insert_series_calls[0]["payment_hold_expires_at"] == expires_at


@pytest.mark.asyncio
async def test_create_series_uses_configured_hold_day_count(monkeypatch):
    pre_noon = datetime(2025, 12, 8, 16, 59, tzinfo=timezone.utc)
    setting_stub = StubSettingService(max_booking_lines=10, pending_payment_hold_days=2)
    service, series_stub, *_ = _service(monkeypatch, setting_stub=setting_stub, now_utc=lambda: pre_noon)
    result = await service.create_series(_command())
    expires_at = datetime(2025, 12, 10, 17, 0, tzinfo=timezone.utc)
    assert result.payment_hold_expires_at == expires_at
    assert series_stub.insert_series_calls[0]["payment_hold_expires_at"] == expires_at


@pytest.mark.asyncio
async def test_create_series_does_not_rewrite_an_existing_series_hold(monkeypatch):
    stored_expires_at = datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc)
    existing_id = uuid4()
    series_stub = StubRecurringBookingRepository(
        series_by_id={
            existing_id: RecurringBookingSeriesResult(
                id=existing_id,
                user_id=uuid4(),
                first_occurrence_date=FIRST_TUESDAY,
                last_occurrence_date=LAST_TUESDAY,
                local_start_time=time(10, 0),
                local_end_time=time(12, 0),
                status=BookingStatus.PENDING_PAYMENT.value,
                payment_hold_expires_at=stored_expires_at,
                quoted_amount=Decimal("400"),
                currency="CAD",
                occurrence_count=4,
            )
        }
    )
    service, series_stub, *_ = _service(monkeypatch, series_stub=series_stub)
    await service.create_series(_command())
    assert series_stub.series_by_id[existing_id].payment_hold_expires_at == stored_expires_at
    assert series_stub.update_series_calls == []
