"""
RecurringBookingService Series cancellation and read tests.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.commands import CancelRecurringBookingSeriesCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import RecurringBookingOccurrenceResult, RecurringBookingSeriesResult
from portal.domain.facility.constants import BookingStatus, FacilityErrorCode, RecurringCancellationScope
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from portal.libs.consts.permission import Permission
from portal.routers.admin.v1.facility.booking_series import cancel_booking_series, get_booking_series
from portal.routers.apis.v1.facility import cancel_my_booking_series, get_my_booking_series
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


def _user_ctx(monkeypatch, *, user_id, email="booker@efcnewlife.org", username="booker"):
    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.email = email
    ctx.username = username
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
    return ctx


def _occurrence(*, status=BookingStatus.CONFIRMED.value, start_at=None) -> RecurringBookingOccurrenceResult:
    start_at = start_at or datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc)
    return RecurringBookingOccurrenceResult(
        id=uuid4(),
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        status=status,
        quoted_amount=Decimal("100"),
        currency="CAD",
        facility_ids=[new_uuid()],
    )


def _series(*, series_id=None, user_id=None, status=BookingStatus.CONFIRMED.value, expires_at=None, occurrences=None) -> RecurringBookingSeriesResult:
    series_id = series_id or uuid4()
    user_id = user_id or uuid4()
    occurrences = occurrences or [
        _occurrence(start_at=datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc)),
        _occurrence(start_at=datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc)),
        _occurrence(start_at=datetime(2026, 3, 24, 15, 0, tzinfo=timezone.utc)),
        _occurrence(start_at=datetime(2026, 3, 31, 15, 0, tzinfo=timezone.utc)),
    ]
    return RecurringBookingSeriesResult(
        id=series_id,
        user_id=user_id,
        first_occurrence_date=date(2026, 2, 17),
        last_occurrence_date=date(2026, 3, 31),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status=status,
        payment_hold_expires_at=expires_at,
        quoted_amount=Decimal("400"),
        currency="CAD",
        occurrence_count=len(occurrences),
        occurrences=occurrences,
    )


def _service(monkeypatch, *, operator_id=None, series_stub=None, booking_stub=None, ministry_stub=None):
    operator_id = operator_id or uuid4()
    _user_ctx(monkeypatch, user_id=operator_id)
    series_stub = series_stub or StubRecurringBookingRepository()
    booking_stub = booking_stub or StubBookingRepository()
    service = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
        ministry_repository=ministry_stub or StubMinistryRepository(),
        room_blackout_repository=StubRoomBlackoutRepository(),
        setting_service=StubSettingService(max_booking_lines=10),
        user_read_service=StubUserReadService(),
        override_log_repository=StubOverrideLogRepository(),
        override_notifier=StubRecurringOverrideNotifier(),
        expiry_notifier=StubRecurringExpiryNotifier(),
        now_utc=lambda: NOW,
    )
    return service, series_stub, booking_stub, operator_id


def _seed_series(series_stub, booking_stub, series: RecurringBookingSeriesResult) -> RecurringBookingSeriesResult:
    series_stub.series_by_id[series.id] = series
    booking_stub.series_occurrences[series.id] = list(series.occurrences)
    return series


@pytest.mark.asyncio
async def test_cancel_series_rejects_unknown_scope(monkeypatch):
    series = _series()
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    with pytest.raises(BadRequestException) as exc_info:
        await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope="single"))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_INVALID_CANCELLATION_SCOPE.value
    assert booking_stub.cancel_calls == []


@pytest.mark.asyncio
async def test_cancel_occurrence_cancels_that_future_occurrence_only(monkeypatch):
    series = _series()
    historical, selected, later, last = series.occurrences
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, operator_id = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=selected.id, cancel_reason="one week")
    )

    assert {item.id: item.status for item in result.occurrences} == {
        historical.id: BookingStatus.CONFIRMED.value,
        selected.id: BookingStatus.CANCELLED.value,
        later.id: BookingStatus.CONFIRMED.value,
        last.id: BookingStatus.CONFIRMED.value,
    }
    assert result.status == BookingStatus.CONFIRMED.value
    assert booking_stub.cancel_calls == [dict(booking_id=selected.id, cancelled_by_id=operator_id, cancel_reason="one week", cancel_slots=True)]
    assert series_stub.update_series_calls == []


@pytest.mark.asyncio
async def test_cancel_this_and_future_leaves_earlier_occurrences(monkeypatch):
    series = _series()
    historical, selected, later, last = series.occurrences
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, operator_id = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value, occurrence_id=selected.id)
    )

    assert result.status == BookingStatus.CANCELLED.value
    assert {item.id: item.status for item in result.occurrences} == {
        historical.id: BookingStatus.CONFIRMED.value,
        selected.id: BookingStatus.CANCELLED.value,
        later.id: BookingStatus.CANCELLED.value,
        last.id: BookingStatus.CANCELLED.value,
    }
    cancelled_ids = {call["booking_id"] for call in booking_stub.cancel_calls}
    assert cancelled_ids == {selected.id, later.id, last.id}
    assert all(call["cancelled_by_id"] == operator_id for call in booking_stub.cancel_calls)
    assert all(call["cancel_slots"] is True for call in booking_stub.cancel_calls)
    assert historical.id not in cancelled_ids
    assert series_stub.update_series_calls[0]["status"] == BookingStatus.CANCELLED.value
    assert series_stub.update_series_calls[0]["payment_hold_expires_at"] is None


@pytest.mark.asyncio
async def test_cancel_this_and_future_keeps_earlier_future_occurrence(monkeypatch):
    series = _series()
    historical, first_future, selected, last = series.occurrences
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value, occurrence_id=selected.id)
    )

    assert result.status == BookingStatus.CONFIRMED.value
    assert {item.id: item.status for item in result.occurrences} == {
        historical.id: BookingStatus.CONFIRMED.value,
        first_future.id: BookingStatus.CONFIRMED.value,
        selected.id: BookingStatus.CANCELLED.value,
        last.id: BookingStatus.CANCELLED.value,
    }
    assert {call["booking_id"] for call in booking_stub.cancel_calls} == {selected.id, last.id}
    assert series_stub.update_series_calls == []


@pytest.mark.asyncio
async def test_cancel_entire_series_tolerates_naive_utc_occurrence_start_at(monkeypatch):
    """asyncpg often returns timestamptz as naive UTC; cancel must not TypeError vs aware now."""
    booker_id = uuid4()
    historical = _occurrence(start_at=datetime(2026, 2, 17, 15, 0))
    future = _occurrence(start_at=datetime(2026, 3, 17, 15, 0))
    later = _occurrence(start_at=datetime(2026, 3, 24, 15, 0))
    assert historical.start_at.tzinfo is None
    assert future.start_at.tzinfo is None
    series = _series(user_id=booker_id, occurrences=[historical, future, later])
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, operator_id=booker_id, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_my_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value, cancel_reason="No needed")
    )

    assert result.status == BookingStatus.CANCELLED.value
    assert {item.id: item.status for item in result.occurrences} == {
        historical.id: BookingStatus.CONFIRMED.value,
        future.id: BookingStatus.CANCELLED.value,
        later.id: BookingStatus.CANCELLED.value,
    }
    assert {call["booking_id"] for call in booking_stub.cancel_calls} == {future.id, later.id}


@pytest.mark.asyncio
async def test_cancel_occurrence_and_this_and_future_tolerate_naive_utc_start_at(monkeypatch):
    historical = _occurrence(start_at=datetime(2026, 2, 17, 15, 0))
    selected = _occurrence(start_at=datetime(2026, 3, 17, 15, 0))
    later = _occurrence(start_at=datetime(2026, 3, 24, 15, 0))
    series = _series(occurrences=[historical, selected, later])
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    with pytest.raises(BadRequestException) as exc_info:
        await service.cancel_series(
            series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=historical.id)
        )
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_HISTORICAL_OCCURRENCE.value

    occurrence_result = await service.cancel_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=selected.id, cancel_reason="one week")
    )
    assert {item.id: item.status for item in occurrence_result.occurrences}[selected.id] == BookingStatus.CANCELLED.value

    booking_stub.cancel_calls.clear()
    this_and_future = await service.cancel_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value, occurrence_id=later.id)
    )
    assert {call["booking_id"] for call in booking_stub.cancel_calls} == {later.id}
    assert this_and_future.status == BookingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_cancel_entire_series_keeps_historical_and_overridden_rows(monkeypatch):
    overridden = _occurrence(status=BookingStatus.OVERRIDDEN.value, start_at=datetime(2026, 3, 3, 15, 0, tzinfo=timezone.utc))
    historical = _occurrence(start_at=datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc))
    future = _occurrence(start_at=datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc))
    pending = _occurrence(status=BookingStatus.PENDING_PAYMENT.value, start_at=datetime(2026, 3, 24, 15, 0, tzinfo=timezone.utc))
    series = _series(status=BookingStatus.PENDING_PAYMENT.value, expires_at=NOW + timedelta(hours=24), occurrences=[overridden, historical, future, pending])
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, operator_id = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))

    assert result.status == BookingStatus.CANCELLED.value
    assert result.payment_hold_expires_at is None
    assert {item.id: item.status for item in result.occurrences} == {
        overridden.id: BookingStatus.OVERRIDDEN.value,
        historical.id: BookingStatus.CONFIRMED.value,
        future.id: BookingStatus.CANCELLED.value,
        pending.id: BookingStatus.CANCELLED.value,
    }
    assert {call["booking_id"] for call in booking_stub.cancel_calls} == {future.id, pending.id}
    assert all(call["cancelled_by_id"] == operator_id for call in booking_stub.cancel_calls)
    assert series_stub.update_series_calls[0]["id"] == series.id


@pytest.mark.asyncio
async def test_cancel_occurrence_rejects_historical_occurrence(monkeypatch):
    series = _series()
    historical = series.occurrences[0]
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    with pytest.raises(BadRequestException) as exc_info:
        await service.cancel_series(
            series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=historical.id)
        )
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_HISTORICAL_OCCURRENCE.value
    assert booking_stub.cancel_calls == []
    assert historical.status == BookingStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_cancel_this_and_future_requires_occurrence_id(monkeypatch):
    series = _series()
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    with pytest.raises(BadRequestException) as exc_info:
        await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_OCCURRENCE_REQUIRED.value


@pytest.mark.asyncio
async def test_cancel_series_rejects_missing_series_and_occurrence(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(NotFoundException) as exc_info:
        await service.cancel_series(uuid4(), CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value

    series = _series()
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)
    with pytest.raises(NotFoundException) as exc_info:
        await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=uuid4()))
    assert exc_info.value.error_code == FacilityErrorCode.RECURRING_OCCURRENCE_NOT_FOUND.value


@pytest.mark.asyncio
async def test_cancel_entire_series_is_idempotent(monkeypatch):
    series = _series()
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    first = await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))
    second = await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))

    assert first.status == BookingStatus.CANCELLED.value
    assert second.status == BookingStatus.CANCELLED.value
    assert len(booking_stub.cancel_calls) == 3
    assert len(series_stub.update_series_calls) == 1


@pytest.mark.asyncio
async def test_cancel_occurrence_is_idempotent(monkeypatch):
    series = _series()
    selected = series.occurrences[1]
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)
    command = CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.OCCURRENCE.value, occurrence_id=selected.id)

    first = await service.cancel_series(series.id, command)
    second = await service.cancel_series(series.id, command)

    assert first.occurrences[1].status == BookingStatus.CANCELLED.value
    assert second.occurrences[1].status == BookingStatus.CANCELLED.value
    assert len(booking_stub.cancel_calls) == 1
    assert first.status == BookingStatus.CONFIRMED.value
    assert second.status == BookingStatus.CONFIRMED.value


@pytest.mark.asyncio
async def test_cancel_this_and_future_is_idempotent(monkeypatch):
    series = _series()
    selected = series.occurrences[2]
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)
    command = CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value, occurrence_id=selected.id)

    await service.cancel_series(series.id, command)
    await service.cancel_series(series.id, command)

    assert len(booking_stub.cancel_calls) == 2
    assert series_stub.update_series_calls == []


@pytest.mark.asyncio
async def test_cancel_my_series_is_owner_only(monkeypatch):
    booker_id = uuid4()
    series = _series(user_id=booker_id)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, operator_id=uuid4(), series_stub=series_stub, booking_stub=booking_stub)

    with pytest.raises(NotFoundException) as exc_info:
        await service.cancel_my_series(
            series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value, cancel_reason="Moving")
        )
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value
    assert booking_stub.cancel_calls == []

    owner_service, series_stub, booking_stub, _ = _service(monkeypatch, operator_id=booker_id, series_stub=series_stub, booking_stub=booking_stub)
    result = await owner_service.cancel_my_series(
        series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value, cancel_reason="Moving")
    )
    assert result.status == BookingStatus.CANCELLED.value
    assert booking_stub.cancel_calls


@pytest.mark.asyncio
async def test_admin_cancel_series_does_not_require_booker_identity(monkeypatch):
    booker_id = uuid4()
    series = _series(user_id=booker_id)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, _, booking_stub, operator_id = _service(monkeypatch, operator_id=uuid4(), series_stub=series_stub, booking_stub=booking_stub)

    result = await service.cancel_series(series.id, CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))

    assert result.status == BookingStatus.CANCELLED.value
    assert operator_id != booker_id
    assert all(call["cancelled_by_id"] == operator_id for call in booking_stub.cancel_calls)


@pytest.mark.asyncio
async def test_get_series_exposes_occurrence_and_payment_state(monkeypatch):
    cancelled = _occurrence(status=BookingStatus.CANCELLED.value, start_at=datetime(2026, 2, 17, 15, 0, tzinfo=timezone.utc))
    pending = _occurrence(status=BookingStatus.PENDING_PAYMENT.value, start_at=datetime(2026, 3, 17, 15, 0, tzinfo=timezone.utc))
    expires_at = NOW + timedelta(hours=36)
    series = _series(status=BookingStatus.PENDING_PAYMENT.value, expires_at=expires_at, occurrences=[cancelled, pending])
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.get_series(series.id)

    assert result.status == BookingStatus.PENDING_PAYMENT.value
    assert result.payment_hold_expires_at == expires_at
    assert result.quoted_amount == Decimal("400")
    assert [item.status for item in result.occurrences] == [BookingStatus.CANCELLED.value, BookingStatus.PENDING_PAYMENT.value]


@pytest.mark.asyncio
async def test_get_my_series_is_owner_only(monkeypatch):
    booker_id = uuid4()
    series = _series(user_id=booker_id)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_stub, booking_stub, series)
    stranger, *_ = _service(monkeypatch, operator_id=uuid4(), series_stub=series_stub, booking_stub=booking_stub)
    with pytest.raises(NotFoundException) as exc_info:
        await stranger.get_my_series(series.id)
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value

    owner, *_ = _service(monkeypatch, operator_id=booker_id, series_stub=series_stub, booking_stub=booking_stub)
    result = await owner.get_my_series(series.id)
    assert result.id == series.id
    assert result.user_id == booker_id


@pytest.mark.asyncio
async def test_get_series_rejects_missing_series(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(NotFoundException) as exc_info:
        await service.get_series(uuid4())
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value


@pytest.mark.asyncio
async def test_cancel_and_get_require_authenticated_operator(monkeypatch):
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: None)
    service = RecurringBookingService(
        series_repository=StubRecurringBookingRepository(),
        booking_repository=StubBookingRepository(),
        pricing_service=StubPricingService(make_preview_quote_result()),
        ministry_repository=StubMinistryRepository(),
        room_blackout_repository=StubRoomBlackoutRepository(),
        setting_service=StubSettingService(),
        user_read_service=StubUserReadService(),
        override_log_repository=StubOverrideLogRepository(),
        now_utc=lambda: NOW,
    )
    with pytest.raises(ForbiddenException):
        await service.get_series(uuid4())
    with pytest.raises(ForbiddenException):
        await service.cancel_series(uuid4(), CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.ENTIRE_SERIES.value))


def test_admin_series_read_requires_booking_read_permission():
    auth_config = get_booking_series.__auth_config__
    assert auth_config.permission_codes == [Permission.FACILITY_BOOKING.read]
    assert auth_config.is_admin is True


def test_admin_series_cancel_requires_booking_modify_permission():
    auth_config = cancel_booking_series.__auth_config__
    assert auth_config.permission_codes == [Permission.FACILITY_BOOKING.modify]
    assert Permission.FACILITY_BOOKING_PAYMENT.modify not in auth_config.permission_codes
    assert auth_config.is_admin is True


def test_member_series_read_and_cancel_are_not_admin_routes():
    assert get_my_booking_series.__auth_config__.is_admin is False
    assert cancel_my_booking_series.__auth_config__.is_admin is False
