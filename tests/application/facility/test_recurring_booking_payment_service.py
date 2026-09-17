"""
RecurringBookingService payment confirmation and Pending-payment expiry tests.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from inspect import getsource
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.results import PendingPaymentExpirySweepResult, RecurringBookingOccurrenceResult, RecurringBookingSeriesResult
from portal.domain.facility.constants import PENDING_PAYMENT_HOLD_EXPIRED_REASON, BookingStatus, FacilityErrorCode
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.libs.consts.permission import Permission
from portal.routers.admin.v1.facility.booking_series import confirm_booking_series_payment
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

NOW = datetime(2026, 1, 10, 17, 0, tzinfo=timezone.utc)


def _user_ctx(monkeypatch, *, user_id, email="operator@efcnewlife.org", username="payment.operator"):
    class UserCtx:
        pass

    ctx = UserCtx()
    ctx.user_id = user_id
    ctx.email = email
    ctx.username = username
    monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
    return ctx


def _occurrence(series_id, *, status=BookingStatus.PENDING_PAYMENT.value, start_at=None) -> RecurringBookingOccurrenceResult:
    start_at = start_at or datetime(2026, 1, 13, 15, 0, tzinfo=timezone.utc)
    return RecurringBookingOccurrenceResult(
        id=uuid4(),
        start_at=start_at,
        end_at=start_at + timedelta(hours=2),
        status=status,
        quoted_amount=Decimal("100"),
        currency="CAD",
        facility_ids=[new_uuid()],
    )


def _series(*, series_id=None, user_id=None, status=BookingStatus.PENDING_PAYMENT.value, expires_at=None, occurrences=None) -> RecurringBookingSeriesResult:
    series_id = series_id or uuid4()
    user_id = user_id or uuid4()
    occurrences = occurrences or [_occurrence(series_id), _occurrence(series_id, start_at=datetime(2026, 1, 20, 15, 0, tzinfo=timezone.utc))]
    return RecurringBookingSeriesResult(
        id=series_id,
        user_id=user_id,
        first_occurrence_date=date(2026, 1, 13),
        last_occurrence_date=date(2026, 1, 20),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status=status,
        payment_hold_expires_at=expires_at if expires_at is not None else NOW + timedelta(hours=48),
        quoted_amount=Decimal("200"),
        currency="CAD",
        occurrence_count=len(occurrences),
        occurrences=occurrences,
    )


def _service(monkeypatch, *, operator_id=None, series_stub=None, booking_stub=None, expiry_notifier=None, now_utc=None):
    operator_id = operator_id or uuid4()
    _user_ctx(monkeypatch, user_id=operator_id)
    series_stub = series_stub or StubRecurringBookingRepository()
    booking_stub = booking_stub or StubBookingRepository()
    expiry_notifier = expiry_notifier or StubRecurringExpiryNotifier()
    service = RecurringBookingService(
        series_repository=series_stub,
        booking_repository=booking_stub,
        pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
        ministry_repository=StubMinistryRepository(),
        room_blackout_repository=StubRoomBlackoutRepository(),
        setting_service=StubSettingService(max_booking_lines=10),
        user_read_service=StubUserReadService(),
        override_log_repository=StubOverrideLogRepository(),
        override_notifier=StubRecurringOverrideNotifier(),
        expiry_notifier=expiry_notifier,
        now_utc=now_utc or (lambda: NOW),
    )
    return service, series_stub, booking_stub, expiry_notifier, operator_id


def _seed_pending_series(series_stub, booking_stub, series: RecurringBookingSeriesResult) -> RecurringBookingSeriesResult:
    series_stub.series_by_id[series.id] = series
    booking_stub.series_occurrences[series.id] = list(series.occurrences)
    return series


@pytest.mark.asyncio
async def test_confirm_payment_confirms_series_and_pending_occurrences(monkeypatch):
    series = _series()
    cancelled = _occurrence(series.id, status=BookingStatus.CANCELLED.value)
    series.occurrences.append(cancelled)
    series.occurrence_count = len(series.occurrences)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, _, operator_id = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.confirm_payment(series.id)

    assert result.status == BookingStatus.CONFIRMED.value
    assert result.payment_hold_expires_at is None
    assert result.confirmed_by_id == operator_id
    assert series_stub.update_series_calls[0]["id"] == series.id
    assert series_stub.update_series_calls[0]["status"] == BookingStatus.CONFIRMED.value
    assert series_stub.update_series_calls[0]["updated_by_id"] == operator_id
    assert booking_stub.confirm_series_calls == [{"series_id": series.id, "operator_id": operator_id}]
    pending_statuses = [item.status for item in result.occurrences if item.id != cancelled.id]
    assert pending_statuses == [BookingStatus.CONFIRMED.value, BookingStatus.CONFIRMED.value]
    assert next(item.status for item in result.occurrences if item.id == cancelled.id) == BookingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_confirm_payment_is_idempotent_when_already_confirmed(monkeypatch):
    series = _series(status=BookingStatus.CONFIRMED.value, expires_at=None)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.confirm_payment(series.id)

    assert result.status == BookingStatus.CONFIRMED.value
    assert series_stub.update_series_calls == []
    assert booking_stub.confirm_series_calls == []


@pytest.mark.asyncio
async def test_confirm_payment_rejects_missing_series(monkeypatch):
    service, *_ = _service(monkeypatch)
    with pytest.raises(NotFoundException) as exc_info:
        await service.confirm_payment(uuid4())
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value


@pytest.mark.asyncio
async def test_confirm_payment_rejects_cancelled_series(monkeypatch):
    series = _series(status=BookingStatus.CANCELLED.value)
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.confirm_payment(series.id)
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_PENDING_PAYMENT.value


@pytest.mark.asyncio
async def test_confirm_payment_rejects_elapsed_pending_hold(monkeypatch):
    series = _series(expires_at=NOW - timedelta(seconds=1))
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, *_ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.confirm_payment(series.id)
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_PENDING_PAYMENT.value
    assert series_stub.update_series_calls == []
    assert booking_stub.confirm_series_calls == []


@pytest.mark.asyncio
async def test_confirm_payment_requires_authenticated_operator(monkeypatch):
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
        await service.confirm_payment(uuid4())


@pytest.mark.asyncio
async def test_expire_pending_holds_cancels_elapsed_series_and_notifies_booker(monkeypatch):
    series = _series(expires_at=NOW - timedelta(minutes=1))
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, expiry_notifier, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.expire_pending_holds()

    assert isinstance(result, PendingPaymentExpirySweepResult)
    assert result.skipped is False
    assert result.expired_series_ids == [series.id]
    assert series_stub.update_series_calls[0]["status"] == BookingStatus.CANCELLED.value
    assert {call["booking_id"] for call in booking_stub.cancel_calls} == {item.id for item in series.occurrences}
    assert all(call["cancel_slots"] is True for call in booking_stub.cancel_calls)
    assert all(call["cancel_reason"] == PENDING_PAYMENT_HOLD_EXPIRED_REASON for call in booking_stub.cancel_calls)
    assert all(call["cancelled_by_id"] is None for call in booking_stub.cancel_calls)
    assert len(expiry_notifier.calls) == 1
    assert expiry_notifier.calls[0].series_id == series.id
    assert expiry_notifier.calls[0].booker_id == series.user_id
    assert expiry_notifier.calls[0].quoted_amount == Decimal("200")
    assert series_stub.lock_acquire_calls == 1
    assert series_stub.lock_release_calls == 0


@pytest.mark.asyncio
async def test_expire_pending_holds_is_repeat_safe(monkeypatch):
    series = _series(expires_at=NOW - timedelta(minutes=1))
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, expiry_notifier, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    first = await service.expire_pending_holds()
    second = await service.expire_pending_holds()

    assert first.expired_series_ids == [series.id]
    assert second.expired_series_ids == []
    assert len(booking_stub.cancel_calls) == 2
    assert len(expiry_notifier.calls) == 1


@pytest.mark.asyncio
async def test_expire_pending_holds_skips_when_advisory_lock_is_held(monkeypatch):
    series = _series(expires_at=NOW - timedelta(minutes=1))
    series_stub = StubRecurringBookingRepository(lock_acquired=False)
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    service, series_stub, booking_stub, expiry_notifier, _ = _service(monkeypatch, series_stub=series_stub, booking_stub=booking_stub)

    result = await service.expire_pending_holds()

    assert result.skipped is True
    assert result.expired_series_ids == []
    assert series_stub.update_series_calls == []
    assert booking_stub.cancel_calls == []
    assert expiry_notifier.calls == []
    assert series_stub.lock_release_calls == 0


@pytest.mark.asyncio
async def test_expire_pending_holds_keeps_expiry_when_email_fails(monkeypatch):
    series = _series(expires_at=NOW - timedelta(minutes=1))
    series_stub = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_pending_series(series_stub, booking_stub, series)
    expiry_notifier = StubRecurringExpiryNotifier(raise_error=RuntimeError("graph down"))
    service, series_stub, booking_stub, expiry_notifier, _ = _service(
        monkeypatch, series_stub=series_stub, booking_stub=booking_stub, expiry_notifier=expiry_notifier
    )

    result = await service.expire_pending_holds()

    assert result.expired_series_ids == [series.id]
    assert series_stub.update_series_calls[0]["status"] == BookingStatus.CANCELLED.value
    assert len(booking_stub.cancel_calls) == 2
    assert series_stub.lock_release_calls == 0


def test_confirm_payment_route_requires_booking_payment_permission():
    auth_config = confirm_booking_series_payment.__auth_config__
    assert auth_config.permission_codes == [Permission.FACILITY_BOOKING_PAYMENT.modify]
    assert Permission.FACILITY_BOOKING.modify not in auth_config.permission_codes
    assert auth_config.is_admin is True


def test_occupancy_reads_use_query_time_pending_hold_expiry():
    sql = str(BookingRepository._active_occupancy_clause().compile(dialect=postgresql.dialect()))
    assert "payment_hold_expires_at" in sql
    assert "now()" in sql
    assert "BookingStatus.PENDING_PAYMENT" in getsource(BookingRepository._active_occupancy_clause)
    occupancy_methods = (BookingRepository.has_confirmed_slot_overlap, BookingRepository.list_occupying_slots, BookingRepository.list_rental_occurrence_starts)
    for method in occupancy_methods:
        assert "_active_occupancy_clause()" in getsource(method)
