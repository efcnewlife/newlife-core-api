"""
RecurringBookingService Blackout impact preview and cancellation tests.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import (
    BlackoutImpactOccurrenceResult,
    RecurringBookingOccurrenceResult,
    RecurringBookingSeriesResult,
    RoomBlackoutResult,
)
from portal.domain.facility.constants import BookingStatus, RoomBlackoutKind
from tests.fixtures.facility.factories import make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubOverrideLogRepository,
    StubPricingService,
    StubRecurringBookingRepository,
    StubRecurringExpiryNotifier,
    StubRecurringOverrideNotifier,
    StubRoomBlackoutRepository,
    StubUserReadService,
)
from tests.fixtures.system.stubs import StubSettingService

NOW = datetime(2026, 3, 10, 17, 0, tzinfo=timezone.utc)
ROOM_ID = new_uuid()
OTHER_ROOM_ID = new_uuid()


def _user_ctx(monkeypatch, *, user_id, email="operator@efcnewlife.org", username="operator"):
    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.email = email
    ctx.username = username
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
    return ctx


def _one_off_blackout(
    *, facility_id=ROOM_ID, blackout_date=date(2026, 3, 17), start_time=time(10, 0), end_time=time(12, 0), is_active=True
) -> RoomBlackoutResult:
    return RoomBlackoutResult(
        facility_id=facility_id,
        name="Maintenance",
        reason="HVAC work",
        kind=RoomBlackoutKind.ONE_OFF.value,
        blackout_date=blackout_date,
        days_of_week_mask=None,
        start_time=start_time,
        end_time=end_time,
        is_active=is_active,
    )


def _impact_occurrence(
    *, start_at=datetime(2026, 3, 17, 14, 0, tzinfo=timezone.utc), facility_ids=None, ministry_id=None, status=BookingStatus.CONFIRMED.value, series_id=None
) -> BlackoutImpactOccurrenceResult:
    return BlackoutImpactOccurrenceResult(
        series_id=series_id or uuid4(),
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        status=status,
        facility_ids=facility_ids or [ROOM_ID],
        ministry_id=ministry_id,
    )


def _series_occurrence(*, occurrence_id, start_at, status=BookingStatus.CONFIRMED.value) -> RecurringBookingOccurrenceResult:
    return RecurringBookingOccurrenceResult(
        id=occurrence_id,
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        status=status,
        quoted_amount=Decimal("100"),
        currency="CAD",
        facility_ids=[ROOM_ID],
    )


def _series(*, series_id, user_id=None, occurrences=None) -> RecurringBookingSeriesResult:
    occurrences = occurrences or []
    return RecurringBookingSeriesResult(
        id=series_id,
        user_id=user_id or uuid4(),
        first_occurrence_date=date(2026, 2, 17),
        last_occurrence_date=date(2026, 3, 31),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status=BookingStatus.CONFIRMED.value,
        quoted_amount=Decimal("400"),
        currency="CAD",
        occurrence_count=len(occurrences),
        occurrences=occurrences,
    )


def _service(monkeypatch, *, booking_stub=None, series_stub=None, override_stub=None):
    operator_id = uuid4()
    _user_ctx(monkeypatch, user_id=operator_id)
    booking_stub = booking_stub or StubBookingRepository()
    series_stub = series_stub or StubRecurringBookingRepository()
    override_stub = override_stub or StubOverrideLogRepository()
    service = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
        ministry_repository=StubMinistryRepository(),
        room_blackout_repository=StubRoomBlackoutRepository(),
        setting_service=StubSettingService(),
        user_read_service=StubUserReadService(),
        override_log_repository=override_stub,
        override_notifier=StubRecurringOverrideNotifier(),
        expiry_notifier=StubRecurringExpiryNotifier(),
        now_utc=lambda: NOW,
    )
    return service, booking_stub, series_stub, override_stub, operator_id


@pytest.mark.asyncio
async def test_preview_blackout_impact_is_empty_when_no_occurrences_overlap(monkeypatch):
    service, *_ = _service(monkeypatch)

    result = await service.preview_blackout_impact(_one_off_blackout())

    assert result.confirmation_required is False
    assert result.items == []


@pytest.mark.asyncio
async def test_preview_blackout_impact_lists_only_overlapping_future_occurrences(monkeypatch):
    impacted = _impact_occurrence()
    later_same_room = _impact_occurrence(start_at=datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc))
    other_room = _impact_occurrence(facility_ids=[OTHER_ROOM_ID])
    historical = _impact_occurrence(start_at=datetime(2026, 2, 17, 14, 0, tzinfo=timezone.utc))
    booking_stub = StubBookingRepository()
    booking_stub.live_future_series_occurrences = [impacted, later_same_room, other_room, historical]
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)

    result = await service.preview_blackout_impact(_one_off_blackout())

    assert result.confirmation_required is True
    assert [item.id for item in result.items] == [impacted.id]


@pytest.mark.asyncio
async def test_preview_blackout_impact_includes_ministry_and_rental_series(monkeypatch):
    rental = _impact_occurrence(ministry_id=None)
    ministry = _impact_occurrence(ministry_id=uuid4(), start_at=datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc))
    booking_stub = StubBookingRepository()
    booking_stub.live_future_series_occurrences = [rental, ministry]
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)

    result = await service.preview_blackout_impact(_one_off_blackout())

    assert {item.id: item.ministry_id for item in result.items} == {rental.id: None, ministry.id: ministry.ministry_id}


@pytest.mark.asyncio
async def test_preview_blackout_impact_includes_pending_payment_occurrences(monkeypatch):
    pending = _impact_occurrence(status=BookingStatus.PENDING_PAYMENT.value)
    booking_stub = StubBookingRepository()
    booking_stub.live_future_series_occurrences = [pending]
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)

    result = await service.preview_blackout_impact(_one_off_blackout())

    assert [item.id for item in result.items] == [pending.id]
    assert result.items[0].status == BookingStatus.PENDING_PAYMENT.value


@pytest.mark.asyncio
async def test_preview_blackout_impact_keeps_all_rooms_on_a_room_scoped_blackout(monkeypatch):
    sibling_room = new_uuid()
    multi_room = _impact_occurrence(facility_ids=[ROOM_ID, sibling_room])
    booking_stub = StubBookingRepository()
    booking_stub.live_future_series_occurrences = [multi_room]
    service, *_ = _service(monkeypatch, booking_stub=booking_stub)

    result = await service.preview_blackout_impact(_one_off_blackout())

    assert result.items[0].facility_ids == [ROOM_ID, sibling_room]


@pytest.mark.asyncio
async def test_apply_blackout_impact_cancels_only_confirmed_occurrences(monkeypatch):
    series_id = uuid4()
    impacted = _impact_occurrence(series_id=series_id)
    later = _impact_occurrence(series_id=series_id, start_at=datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc))
    booking_stub = StubBookingRepository()
    booking_stub.series_occurrences[series_id] = [
        _series_occurrence(occurrence_id=impacted.id, start_at=impacted.start_at),
        _series_occurrence(occurrence_id=later.id, start_at=later.start_at),
    ]
    series_stub = StubRecurringBookingRepository()
    series_stub.series_by_id[series_id] = _series(series_id=series_id, occurrences=booking_stub.series_occurrences[series_id])
    override_stub = StubOverrideLogRepository()
    service, booking_stub, series_stub, override_stub, operator_id = _service(
        monkeypatch, booking_stub=booking_stub, series_stub=series_stub, override_stub=override_stub
    )

    result = await service.apply_blackout_impact([impacted], "HVAC work")

    assert [item.id for item in result.items] == [impacted.id]
    assert booking_stub.cancel_calls == [dict(booking_id=impacted.id, cancelled_by_id=operator_id, cancel_reason="HVAC work", cancel_slots=True)]
    assert series_stub.update_series_calls == []
    assert override_stub.insert_calls == []


@pytest.mark.asyncio
async def test_apply_blackout_impact_cancels_series_when_no_live_occurrences_remain(monkeypatch):
    series_id = uuid4()
    impacted = _impact_occurrence(series_id=series_id)
    historical = _series_occurrence(occurrence_id=uuid4(), start_at=datetime(2026, 2, 17, 14, 0, tzinfo=timezone.utc), status=BookingStatus.CONFIRMED.value)
    booking_stub = StubBookingRepository()
    booking_stub.series_occurrences[series_id] = [historical, _series_occurrence(occurrence_id=impacted.id, start_at=impacted.start_at)]
    series_stub = StubRecurringBookingRepository()
    series_stub.series_by_id[series_id] = _series(series_id=series_id, occurrences=booking_stub.series_occurrences[series_id])
    service, booking_stub, series_stub, _, operator_id = _service(monkeypatch, booking_stub=booking_stub, series_stub=series_stub)

    await service.apply_blackout_impact([impacted], "HVAC work")

    assert booking_stub.cancel_calls[0]["booking_id"] == impacted.id
    assert series_stub.update_series_calls[0]["id"] == series_id
    assert series_stub.update_series_calls[0]["status"] == BookingStatus.CANCELLED.value
    assert series_stub.update_series_calls[0]["updated_by_id"] == operator_id


@pytest.mark.asyncio
async def test_apply_blackout_impact_cancels_mixed_ministry_and_rental_occurrences(monkeypatch):
    rental_series_id = uuid4()
    ministry_series_id = uuid4()
    rental = _impact_occurrence(series_id=rental_series_id, ministry_id=None)
    ministry = _impact_occurrence(series_id=ministry_series_id, ministry_id=uuid4(), start_at=datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc))
    later_rental = _impact_occurrence(series_id=rental_series_id, start_at=datetime(2026, 3, 24, 14, 0, tzinfo=timezone.utc))
    later_ministry = _impact_occurrence(series_id=ministry_series_id, start_at=datetime(2026, 3, 24, 15, 0, tzinfo=timezone.utc))
    booking_stub = StubBookingRepository()
    booking_stub.series_occurrences[rental_series_id] = [
        _series_occurrence(occurrence_id=rental.id, start_at=rental.start_at),
        _series_occurrence(occurrence_id=later_rental.id, start_at=later_rental.start_at),
    ]
    booking_stub.series_occurrences[ministry_series_id] = [
        _series_occurrence(occurrence_id=ministry.id, start_at=ministry.start_at),
        _series_occurrence(occurrence_id=later_ministry.id, start_at=later_ministry.start_at),
    ]
    series_stub = StubRecurringBookingRepository()
    series_stub.series_by_id[rental_series_id] = _series(series_id=rental_series_id, occurrences=booking_stub.series_occurrences[rental_series_id])
    series_stub.series_by_id[ministry_series_id] = _series(series_id=ministry_series_id, occurrences=booking_stub.series_occurrences[ministry_series_id])
    service, booking_stub, series_stub, _, operator_id = _service(monkeypatch, booking_stub=booking_stub, series_stub=series_stub)

    result = await service.apply_blackout_impact([rental, ministry], "HVAC work")

    assert {item.id for item in result.items} == {rental.id, ministry.id}
    assert [call["booking_id"] for call in booking_stub.cancel_calls] == [rental.id, ministry.id]
    assert all(call["cancelled_by_id"] == operator_id for call in booking_stub.cancel_calls)
    assert series_stub.update_series_calls == []
