"""Participant-authorized Booking and Series detail tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from portal.application.content.results import FileGridItemResult
from portal.application.facility.commands import CancelBookingCommand, CancelRecurringBookingSeriesCommand, UpdateTitleCommand
from portal.application.facility.mappers import member_booking_detail_to_api
from portal.application.facility.participant_detail import assemble_participant_booking_detail
from portal.application.facility.results import BookingDetailResult, BookingRoomLineResult, RecurringBookingOccurrenceResult, RecurringBookingSeriesResult
from portal.domain.facility.constants import BookingLifecycleEventKind, BookingStatus, BookingType, FacilityErrorCode, RecurringCancellationScope
from portal.exceptions.responses import BadRequestException, ForbiddenException, NotFoundException
from portal.routers.apis.v1.facility import cancel_my_booking, get_my_booking, get_my_booking_series
from portal.routers.apis.v1.facility import router as member_facility_router
from portal.serializers.apis.v1.facility import MemberBookingCancel, MemberRecurringBookingSeriesCancel
from tests.application.facility.test_booking_service import _booking_service, _user_ctx
from tests.application.facility.test_recurring_booking_cancellation_service import NOW as SERIES_NOW
from tests.application.facility.test_recurring_booking_cancellation_service import _seed_series, _series
from tests.application.facility.test_recurring_booking_cancellation_service import _service as _series_service
from tests.fixtures.facility.stubs import StubBookingRepository, StubFileService, StubMinistryRepository, StubRecurringBookingRepository

NOW = datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc)
CREATED_AT = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)


def _detail(
    *,
    booking_id,
    user_id,
    ministry_id=None,
    status=BookingStatus.CONFIRMED.value,
    start_at=None,
    cancelled_at=None,
    cancel_reason=None,
    created_by="operator.admin",
    payment_hold_expires_at=None,
    series_id=None,
    title="Choir practice",
):
    start_at = start_at or datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    end_at = start_at + timedelta(hours=2)
    room_id = uuid4()
    return BookingDetailResult(
        id=booking_id,
        title=title,
        user_id=user_id,
        user_email="booker@efcnewlife.org",
        user_display_name="Jane Booker",
        ministry_id=ministry_id,
        ministry_name="Choir" if ministry_id else None,
        booking_type=BookingType.RECURRING.value if series_id else BookingType.ONE_TIME.value,
        series_id=series_id,
        start_at=start_at,
        end_at=end_at,
        status=status,
        remark="Bring scores",
        subtotal_amount=Decimal("100"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
        surcharge_amount=Decimal("15"),
        quoted_amount=Decimal("115"),
        currency="CAD",
        cancelled_at=cancelled_at,
        cancel_reason=cancel_reason,
        created_at=CREATED_AT,
        created_by=created_by,
        created_by_id=uuid4(),
        payment_hold_expires_at=payment_hold_expires_at,
        rooms=[
            BookingRoomLineResult(
                id=uuid4(),
                facility_id=room_id,
                facility_name="Gym",
                start_at=start_at,
                end_at=end_at,
                sequence=0,
                billed_hours=Decimal("2"),
                rental_rate_name="Hourly",
                billing_unit="hourly",
                unit_amount=Decimal("50"),
                currency="CAD",
                line_subtotal=Decimal("100"),
            )
        ],
    )


def _file_service(room_id, url="https://files.example/gym.jpg"):
    return StubFileService(
        files_by_resource={
            room_id: [FileGridItemResult(id=uuid4(), original_name="gym.jpg", key="gym", storage="s3", bucket="b", region="ca-central-1", url=url)]
        }
    )


@pytest.mark.asyncio
async def test_booker_reads_complete_participant_booking_detail(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    detail = _detail(booking_id=booking_id, user_id=owner_id)
    room_id = detail.rooms[0].facility_id
    service = _booking_service(StubBookingRepository(detail=detail), file_service=_file_service(room_id))
    result = await service.get_my_booking_by_id(booking_id, now=NOW)
    assert result.title == "Choir practice"
    assert result.remark == "Bring scores"
    assert result.booker_display_name == "Jane Booker"
    assert result.booker_email == "booker@efcnewlife.org"
    assert result.quoted_amount == Decimal("115")
    assert result.subtotal_amount == Decimal("100")
    assert result.surcharge_amount == Decimal("15")
    assert result.rooms[0].facility_name == "Gym"
    assert result.rooms[0].photo_urls == ["https://files.example/gym.jpg"]
    assert result.rooms[0].start_at == detail.start_at
    assert result.is_booker is True
    assert result.is_view_only is False
    assert result.actions.can_edit_title is True
    assert result.actions.can_cancel is True
    assert [event.kind for event in result.timeline] == [BookingLifecycleEventKind.CREATED.value]


@pytest.mark.asyncio
async def test_current_ministry_member_reads_view_only_booking_detail(monkeypatch):
    member_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    _user_ctx(monkeypatch, user_id=member_id)
    booking_id = uuid4()
    detail = _detail(booking_id=booking_id, user_id=booker_id, ministry_id=ministry_id)
    service = _booking_service(StubBookingRepository(detail=detail), ministry_stub=StubMinistryRepository(owned_active_ids=[ministry_id]))
    result = await service.get_my_booking_by_id(booking_id, now=NOW)
    assert result.is_booker is False
    assert result.is_view_only is True
    assert result.booker_email == "booker@efcnewlife.org"
    assert result.actions.can_edit_title is False
    assert result.actions.can_cancel is False
    assert result.actions.can_view_payment_instructions is False
    assert result.actions.can_book_again is False


@pytest.mark.asyncio
async def test_former_member_and_unrelated_user_get_non_disclosing_not_found(monkeypatch):
    booker_id = uuid4()
    ministry_id = uuid4()
    booking_id = uuid4()
    detail = _detail(booking_id=booking_id, user_id=booker_id, ministry_id=ministry_id)
    _user_ctx(monkeypatch, user_id=uuid4())
    former = _booking_service(StubBookingRepository(detail=detail), ministry_stub=StubMinistryRepository(owned_active_ids=[]))
    with pytest.raises(NotFoundException) as former_exc:
        await former.get_my_booking_by_id(booking_id, now=NOW)
    assert former_exc.value.error_code == FacilityErrorCode.BOOKING_NOT_FOUND.value

    unrelated = _booking_service(StubBookingRepository(detail=_detail(booking_id=booking_id, user_id=booker_id)))
    with pytest.raises(NotFoundException) as unrelated_exc:
        await unrelated.get_my_booking_by_id(booking_id, now=NOW)
    assert unrelated_exc.value.error_code == FacilityErrorCode.BOOKING_NOT_FOUND.value


@pytest.mark.asyncio
async def test_timeline_omits_operator_identity_and_replacement_activity(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    detail = _detail(
        booking_id=booking_id,
        user_id=owner_id,
        status=BookingStatus.OVERRIDDEN.value,
        cancelled_at=datetime(2026, 9, 10, 15, 0, tzinfo=timezone.utc),
        cancel_reason="Replaced by choir ministry",
        created_by="operator.admin",
    )
    service = _booking_service(StubBookingRepository(detail=detail))
    result = await service.get_my_booking_by_id(booking_id, now=NOW)
    dumped = result.model_dump()
    assert "created_by" not in dumped
    assert "created_by_id" not in dumped
    assert [event.kind for event in result.timeline] == [BookingLifecycleEventKind.CREATED.value, BookingLifecycleEventKind.OVERRIDDEN.value]
    assert result.timeline[1].reason is None
    assert result.actions.can_book_again is True
    assert result.actions.book_again_date is not None


@pytest.mark.asyncio
async def test_booker_payment_instructions_only_while_hold_is_unexpired(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    live = _detail(
        booking_id=booking_id,
        user_id=owner_id,
        status=BookingStatus.PENDING_PAYMENT.value,
        payment_hold_expires_at=NOW + timedelta(hours=12),
        series_id=uuid4(),
    )
    live_result = await _booking_service(StubBookingRepository(detail=live)).get_my_booking_by_id(booking_id, now=NOW)
    assert live_result.actions.can_view_payment_instructions is True
    assert live_result.payment_hold_expires_at == live.payment_hold_expires_at

    expired = live.model_copy(update={"payment_hold_expires_at": NOW - timedelta(hours=1)})
    expired_result = await _booking_service(StubBookingRepository(detail=expired)).get_my_booking_by_id(booking_id, now=NOW)
    assert expired_result.actions.can_view_payment_instructions is False

    member_id = uuid4()
    _user_ctx(monkeypatch, user_id=member_id)
    ministry_id = uuid4()
    viewer_detail = live.model_copy(update={"ministry_id": ministry_id})
    viewer = _booking_service(StubBookingRepository(detail=viewer_detail), ministry_stub=StubMinistryRepository(owned_active_ids=[ministry_id]))
    viewer_result = await viewer.get_my_booking_by_id(booking_id, now=NOW)
    assert viewer_result.actions.can_view_payment_instructions is False
    assert viewer_result.payment_hold_expires_at is None


@pytest.mark.asyncio
async def test_member_cancel_requires_trimmed_reason(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    stub = StubBookingRepository(detail=_detail(booking_id=booking_id, user_id=owner_id))
    service = _booking_service(stub)
    with pytest.raises(BadRequestException) as exc_info:
        await service.cancel_my_booking(booking_id, CancelBookingCommand(scope="single", cancel_reason="  "))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_CANCEL_REASON_INVALID.value
    await service.cancel_my_booking(booking_id, CancelBookingCommand(scope="single", cancel_reason="  Schedule conflict  "))
    assert stub.cancel_calls[0]["cancel_reason"] == "Schedule conflict"


@pytest.mark.asyncio
async def test_view_only_participant_cannot_cancel(monkeypatch):
    member_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    _user_ctx(monkeypatch, user_id=member_id)
    booking_id = uuid4()
    service = _booking_service(
        StubBookingRepository(detail=_detail(booking_id=booking_id, user_id=booker_id, ministry_id=ministry_id)),
        ministry_stub=StubMinistryRepository(owned_active_ids=[ministry_id]),
    )
    with pytest.raises(ForbiddenException):
        await service.cancel_my_booking(booking_id, CancelBookingCommand(scope="single", cancel_reason="Not my booking"))


@pytest.mark.asyncio
async def test_view_only_participant_cannot_update_title(monkeypatch):
    member_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    _user_ctx(monkeypatch, user_id=member_id)
    booking_id = uuid4()
    service = _booking_service(
        StubBookingRepository(detail=_detail(booking_id=booking_id, user_id=booker_id, ministry_id=ministry_id)),
        ministry_stub=StubMinistryRepository(owned_active_ids=[ministry_id]),
    )
    with pytest.raises(ForbiddenException):
        await service.update_my_booking_title(booking_id, UpdateTitleCommand(title="Hijack"))


@pytest.mark.asyncio
async def test_member_series_this_and_future_applies_one_reason_to_all_targets(monkeypatch):
    booker_id = uuid4()
    series = _series(user_id=booker_id)
    series_repo = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_repo, booking_stub, series)
    service, _, booking_stub, _ = _series_service(monkeypatch, operator_id=booker_id, series_stub=series_repo, booking_stub=booking_stub)
    pivot = series.occurrences[2]
    await service.cancel_my_series(
        series.id,
        CancelRecurringBookingSeriesCommand(scope=RecurringCancellationScope.THIS_AND_FUTURE.value, occurrence_id=pivot.id, cancel_reason="  Family trip  "),
    )
    reasons = [call["cancel_reason"] for call in booking_stub.cancel_calls]
    assert reasons == ["Family trip", "Family trip"]


@pytest.mark.asyncio
async def test_current_ministry_member_reads_complete_series_occurrences(monkeypatch):
    member_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    series_id = uuid4()
    occurrence = RecurringBookingOccurrenceResult(
        id=uuid4(),
        title="Week 1",
        start_at=datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 10, 8, 16, 0, tzinfo=timezone.utc),
        status=BookingStatus.CONFIRMED.value,
        quoted_amount=Decimal("100"),
        currency="CAD",
        facility_ids=[uuid4()],
    )
    series = RecurringBookingSeriesResult(
        id=series_id,
        title="Weekly choir",
        user_id=booker_id,
        ministry_id=ministry_id,
        ministry_name="Choir",
        remark="Bring scores",
        first_occurrence_date=occurrence.start_at.date(),
        last_occurrence_date=occurrence.start_at.date(),
        local_start_time=occurrence.start_at.time(),
        local_end_time=occurrence.end_at.time(),
        status=BookingStatus.CONFIRMED.value,
        quoted_amount=Decimal("100"),
        currency="CAD",
        occurrence_count=1,
        occurrences=[occurrence],
        created_at=CREATED_AT,
        user_email="booker@efcnewlife.org",
        user_display_name="Jane Booker",
    )
    series_repo = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository(
        detail=_detail(booking_id=occurrence.id, user_id=booker_id, ministry_id=ministry_id, series_id=series_id, title="Week 1")
    )
    _seed_series(series_repo, booking_stub, series)
    service, *_ = _series_service(
        monkeypatch,
        operator_id=member_id,
        series_stub=series_repo,
        booking_stub=booking_stub,
        ministry_stub=StubMinistryRepository(owned_active_ids=[ministry_id]),
    )
    result = await service.get_my_series_detail(series_id, now=NOW)
    assert result.title == "Weekly choir"
    assert result.remark == "Bring scores"
    assert result.booker_email == "booker@efcnewlife.org"
    assert result.is_view_only is True
    assert result.actions.can_book_again is False
    assert result.occurrences[0].title == "Week 1"
    assert result.occurrences[0].booker_display_name == "Jane Booker"
    assert result.occurrences[0].timeline[0].kind == BookingLifecycleEventKind.CREATED.value


@pytest.mark.asyncio
async def test_unrelated_user_series_detail_is_not_found(monkeypatch):
    booker_id = uuid4()
    series = _series(user_id=booker_id)
    series_repo = StubRecurringBookingRepository()
    booking_stub = StubBookingRepository()
    _seed_series(series_repo, booking_stub, series)
    stranger, *_ = _series_service(monkeypatch, operator_id=uuid4(), series_stub=series_repo, booking_stub=booking_stub)
    with pytest.raises(NotFoundException) as exc_info:
        await stranger.get_my_series_detail(series.id, now=SERIES_NOW)
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value


def test_member_booking_detail_api_omits_operator_and_exposes_actions():
    owner_id = uuid4()
    booking_id = uuid4()
    detail = _detail(booking_id=booking_id, user_id=owner_id)
    assembled = assemble_participant_booking_detail(
        detail,
        viewer_id=owner_id,
        now=NOW,
        facility_tz=ZoneInfo("America/Toronto"),
        photo_urls_by_room={detail.rooms[0].facility_id: ["https://files.example/gym.jpg"]},
    )
    dumped = member_booking_detail_to_api(assembled).model_dump(by_alias=True)
    assert "createdBy" not in dumped
    assert dumped["bookerDisplayName"] == "Jane Booker"
    assert dumped["bookerEmail"] == "booker@efcnewlife.org"
    assert dumped["rooms"][0]["photoUrls"] == ["https://files.example/gym.jpg"]
    assert dumped["actions"]["canEditTitle"] is True
    assert dumped["timeline"][0]["kind"] == BookingLifecycleEventKind.CREATED.value


def test_member_cancel_serializers_require_reason():
    with pytest.raises(ValidationError):
        MemberBookingCancel(scope="single", cancel_reason="  ")
    with pytest.raises(ValidationError):
        MemberRecurringBookingSeriesCancel(scope="entire_series", cancel_reason="")
    assert MemberBookingCancel(scope="single", cancel_reason="  Moving  ").cancel_reason == "Moving"


def test_member_detail_routes_remain_non_admin():
    routes = {(route.path, method) for route in member_facility_router.routes for method in route.methods}
    assert ("/bookings/{booking_id}", "GET") in routes
    assert ("/booking-series/{series_id}", "GET") in routes
    assert get_my_booking.__auth_config__.is_admin is False
    assert get_my_booking_series.__auth_config__.is_admin is False
    assert cancel_my_booking.__auth_config__.is_admin is False
