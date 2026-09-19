"""Booking and Recurring Booking Series title contract tests."""

from datetime import datetime, time, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from pydantic import ValidationError

from portal.application.facility.commands import CreateBookingCommand, CreateRecurringBookingSeriesCommand, MemberBrowseQueryCommand, UpdateTitleCommand
from portal.application.facility.mappers import (
    create_booking_to_command,
    create_recurring_booking_series_to_command,
    member_booking_detail_to_api,
    recurring_booking_series_to_member_api,
    update_booking_to_command,
    update_title_to_command,
)
from portal.application.facility.participant_detail import assemble_participant_booking_detail
from portal.application.facility.results import BookingDetailResult, MemberBrowseBookingResult, RecurringBookingOccurrenceResult, RecurringBookingSeriesResult
from portal.domain.facility.constants import BookingStatus, FacilityErrorCode, MyBookingsSection
from portal.exceptions.responses import BadRequestException, NotFoundException
from portal.routers.apis.v1.facility import router as member_facility_router
from portal.serializers.admin.v1.facility.booking import AdminBookingCreate, AdminBookingRoomInput, AdminBookingUpdate
from portal.serializers.apis.v1.facility import (
    MemberBookingCreate,
    MemberBookingRoomInput,
    MemberBookingTitleUpdate,
    MemberRecurringBookingSeriesCreate,
    MemberRecurringBookingSeriesProposal,
    MemberRecurringBookingSeriesRoomInput,
)
from tests.application.facility.test_booking_service import _booking_detail, _booking_service, _user_ctx
from tests.application.facility.test_recurring_booking_service import _command, _service
from tests.fixtures.facility.factories import make_create_booking_command
from tests.fixtures.facility.stubs import StubBookingRepository, StubRecurringBookingRepository


def test_create_booking_command_requires_trimmed_plain_text_title():
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    command = CreateBookingCommand(title="  Choir practice  ", start_at=start, end_at=end, rooms=[])
    assert command.title == "Choir practice"
    with pytest.raises(ValidationError):
        CreateBookingCommand(title="", start_at=start, end_at=end, rooms=[])
    with pytest.raises(ValidationError):
        CreateBookingCommand(title="<b>Choir</b>", start_at=start, end_at=end, rooms=[])
    with pytest.raises(ValidationError):
        CreateBookingCommand(title="a" * 31, start_at=start, end_at=end, rooms=[])


def test_create_recurring_series_command_normalizes_title_when_present():
    command = CreateRecurringBookingSeriesCommand(
        title="  Weekly choir  ",
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=_command().rooms,
    )
    assert command.title == "Weekly choir"
    with pytest.raises(ValidationError):
        CreateRecurringBookingSeriesCommand(
            title="<i>Choir</i>",
            first_occurrence_date=_command().first_occurrence_date,
            last_occurrence_date=_command().last_occurrence_date,
            local_start_time=time(10, 0),
            local_end_time=time(12, 0),
            rooms=_command().rooms,
        )


def test_member_create_allows_omitted_title_when_draft_backed_admin_still_requires_it():
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    room = MemberBookingRoomInput(facility_id=uuid4(), start_at=start, end_at=end)
    member = MemberBookingCreate(title="  Gym night  ", start_at=start, end_at=end, rooms=[room])
    assert member.title == "Gym night"
    draft_backed = MemberBookingCreate(start_at=start, end_at=end, rooms=[room], booking_draft_id=uuid4())
    assert draft_backed.title is None
    assert draft_backed.booking_draft_id is not None
    with pytest.raises(ValidationError):
        AdminBookingCreate(user_id=uuid4(), start_at=start, end_at=end, rooms=[AdminBookingRoomInput(facility_id=uuid4())])
    with pytest.raises(ValidationError):
        MemberRecurringBookingSeriesCreate(
            first_occurrence_date=_command().first_occurrence_date,
            last_occurrence_date=_command().last_occurrence_date,
            local_start_time=time(10, 0),
            local_end_time=time(12, 0),
            rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4())],
        )
    created = MemberRecurringBookingSeriesCreate(
        title="Weekly choir",
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4())],
    )
    assert created.title == "Weekly choir"
    proposal = MemberRecurringBookingSeriesProposal(
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4())],
    )
    assert getattr(proposal, "title", None) is None


@pytest.mark.asyncio
async def test_create_booking_persists_title(monkeypatch):
    _user_ctx(monkeypatch)
    stub = StubBookingRepository()
    service = _booking_service(stub)
    await service.create_booking(make_create_booking_command(title="Choir practice"))
    assert stub.insert_calls[0]["title"] == "Choir practice"


@pytest.mark.asyncio
async def test_create_booking_without_draft_requires_title(monkeypatch):
    _user_ctx(monkeypatch)
    service = _booking_service(StubBookingRepository())
    command = make_create_booking_command().model_copy(update={"title": None})
    with pytest.raises(BadRequestException) as exc_info:
        await service.create_booking(command)
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_TITLE_INVALID.value


@pytest.mark.asyncio
async def test_member_booking_read_exposes_title(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    detail = _booking_detail(booking_id=booking_id, user_id=owner_id)
    detail = detail.model_copy(update={"title": "Choir practice"})
    service = _booking_service(StubBookingRepository(detail=detail, participant_bookings=[_list_item(booking_id, owner_id, "Choir practice")]))
    read = await service.get_my_booking_by_id(booking_id)
    assert read.title == "Choir practice"
    items = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.PAST), now=datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc))
    assert items.items[0].booking is not None
    assert items.items[0].booking.title == "Choir practice"


@pytest.mark.asyncio
async def test_booker_can_update_own_booking_title_without_lifecycle_side_effects(monkeypatch):
    owner_id = uuid4()
    _user_ctx(monkeypatch, user_id=owner_id)
    booking_id = uuid4()
    detail = _booking_detail(booking_id=booking_id, user_id=owner_id).model_copy(update={"title": "Choir practice", "status": "confirmed"})
    stub = StubBookingRepository(detail=detail)
    service = _booking_service(stub)
    result = await service.update_my_booking_title(booking_id, UpdateTitleCommand(title="  Special rehearsal  "))
    assert result.title == "Special rehearsal"
    assert stub.update_header_calls == [{"title": "Special rehearsal"}]
    assert stub.cancel_calls == []
    assert stub.override_calls == []
    assert result.status == "confirmed"


@pytest.mark.asyncio
async def test_non_booker_cannot_update_booking_title(monkeypatch):
    _user_ctx(monkeypatch, user_id=uuid4())
    booking_id = uuid4()
    detail = _booking_detail(booking_id=booking_id, user_id=uuid4()).model_copy(update={"title": "Choir practice"})
    service = _booking_service(StubBookingRepository(detail=detail))
    with pytest.raises(NotFoundException) as exc_info:
        await service.update_my_booking_title(booking_id, UpdateTitleCommand(title="Hijack"))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_NOT_FOUND.value


@pytest.mark.asyncio
async def test_missing_booking_title_update_is_not_found(monkeypatch):
    _user_ctx(monkeypatch)
    service = _booking_service(StubBookingRepository(detail=None))
    with pytest.raises(NotFoundException) as exc_info:
        await service.update_my_booking_title(uuid4(), UpdateTitleCommand(title="Choir practice"))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_NOT_FOUND.value


@pytest.mark.asyncio
async def test_create_series_requires_title_and_copies_it_to_occurrences(monkeypatch):
    service, series_stub, booking_stub, _user_id = _service(monkeypatch)
    with pytest.raises(BadRequestException) as missing:
        await service.create_series(_command().model_copy(update={"title": None}))
    assert missing.value.error_code == FacilityErrorCode.BOOKING_TITLE_INVALID.value

    result = await service.create_series(_command(title="Weekly choir"))
    assert result.title == "Weekly choir"
    assert series_stub.insert_series_calls[0]["title"] == "Weekly choir"
    assert all(row["title"] == "Weekly choir" for row in booking_stub.insert_calls)
    assert all(occurrence.title == "Weekly choir" for occurrence in result.occurrences)


@pytest.mark.asyncio
async def test_series_and_occurrence_title_edits_stay_independent(monkeypatch):
    user_id = uuid4()
    series_id = uuid4()
    first_id = uuid4()
    second_id = uuid4()
    occurrences = [
        RecurringBookingOccurrenceResult(
            id=first_id,
            title="Weekly choir",
            start_at=datetime(2026, 1, 6, 15, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 6, 17, 0, tzinfo=timezone.utc),
            status=BookingStatus.PENDING_PAYMENT.value,
            quoted_amount=Decimal("100"),
            currency="CAD",
            facility_ids=[uuid4()],
        ),
        RecurringBookingOccurrenceResult(
            id=second_id,
            title="Weekly choir",
            start_at=datetime(2026, 1, 13, 15, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 1, 13, 17, 0, tzinfo=timezone.utc),
            status=BookingStatus.PENDING_PAYMENT.value,
            quoted_amount=Decimal("100"),
            currency="CAD",
            facility_ids=[uuid4()],
        ),
    ]
    series = RecurringBookingSeriesResult(
        id=series_id,
        title="Weekly choir",
        user_id=user_id,
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status=BookingStatus.PENDING_PAYMENT.value,
        quoted_amount=Decimal("200"),
        currency="CAD",
        occurrence_count=2,
        occurrences=occurrences,
    )
    series_stub = StubRecurringBookingRepository(series_by_id={series_id: series})
    booking_stub = StubBookingRepository()
    booking_stub.series_occurrences[series_id] = list(occurrences)
    service, *_rest = _service(monkeypatch, user_id=user_id, series_stub=series_stub, booking_stub=booking_stub)

    updated_series = await service.update_my_series_title(series_id, UpdateTitleCommand(title="Choir 2026"))
    assert updated_series.title == "Choir 2026"
    assert series_stub.update_series_calls == [{"id": series_id, "title": "Choir 2026"}]
    assert booking_stub.update_header_calls == []
    assert [item.title for item in updated_series.occurrences] == ["Weekly choir", "Weekly choir"]

    _user_ctx(monkeypatch, user_id=user_id)
    booking_stub.detail = BookingDetailResult(
        id=first_id,
        title="Weekly choir",
        user_id=user_id,
        booking_type="recurring",
        series_id=series_id,
        start_at=occurrences[0].start_at,
        end_at=occurrences[0].end_at,
        status=occurrences[0].status,
        quoted_amount=occurrences[0].quoted_amount,
        currency=occurrences[0].currency,
    )
    booking_service = _booking_service(booking_stub)
    occurrence = await booking_service.update_my_booking_title(first_id, UpdateTitleCommand(title="Special week"))
    assert occurrence.title == "Special week"
    assert booking_stub.update_header_calls == [{"title": "Special week"}]
    refreshed = await service.get_my_series(series_id)
    assert refreshed.title == "Choir 2026"
    assert [item.title for item in refreshed.occurrences] == ["Special week", "Weekly choir"]


@pytest.mark.asyncio
async def test_non_booker_cannot_update_series_title(monkeypatch):
    owner_id = uuid4()
    series_id = uuid4()
    series = RecurringBookingSeriesResult(
        id=series_id,
        title="Weekly choir",
        user_id=owner_id,
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status=BookingStatus.PENDING_PAYMENT.value,
        quoted_amount=Decimal("200"),
        currency="CAD",
        occurrence_count=0,
    )
    service, *_rest = _service(monkeypatch, series_stub=StubRecurringBookingRepository(series_by_id={series_id: series}))
    with pytest.raises(NotFoundException) as exc_info:
        await service.update_my_series_title(series_id, UpdateTitleCommand(title="Hijack"))
    assert exc_info.value.error_code == FacilityErrorCode.BOOKING_SERIES_NOT_FOUND.value


def test_mappers_and_member_reads_expose_titles():
    start = datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    admin = AdminBookingCreate(user_id=uuid4(), title="  Admin choir  ", start_at=start, end_at=end, rooms=[AdminBookingRoomInput(facility_id=uuid4())])
    assert create_booking_to_command(admin).title == "Admin choir"
    assert update_booking_to_command(AdminBookingUpdate(title="  Admin edit  ")).title == "Admin edit"
    member_create = MemberRecurringBookingSeriesCreate(
        title="Weekly choir",
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        rooms=[MemberRecurringBookingSeriesRoomInput(facility_id=uuid4())],
    )
    assert create_recurring_booking_series_to_command(member_create).title == "Weekly choir"
    assert update_title_to_command(MemberBookingTitleUpdate(title="  Renamed  ")).title == "Renamed"
    detail = BookingDetailResult(id=uuid4(), title="Choir practice", user_id=uuid4(), booking_type="one_time", start_at=start, end_at=end, status="confirmed")
    assembled = assemble_participant_booking_detail(detail, viewer_id=detail.user_id, now=start, facility_tz=ZoneInfo("America/Toronto"), photo_urls_by_room={})
    assert member_booking_detail_to_api(assembled).title == "Choir practice"
    series = RecurringBookingSeriesResult(
        id=uuid4(),
        title="Weekly choir",
        user_id=uuid4(),
        first_occurrence_date=_command().first_occurrence_date,
        last_occurrence_date=_command().last_occurrence_date,
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        status="pending_payment",
        quoted_amount=Decimal("100"),
        currency="CAD",
        occurrence_count=1,
        occurrences=[
            RecurringBookingOccurrenceResult(
                id=uuid4(), title="Weekly choir", start_at=start, end_at=end, status="pending_payment", quoted_amount=Decimal("100"), currency="CAD"
            )
        ],
    )
    dumped = recurring_booking_series_to_member_api(series).model_dump()
    assert dumped["title"] == "Weekly choir"
    assert dumped["occurrences"][0]["title"] == "Weekly choir"


def test_member_title_update_routes_exist():
    routes = {(route.path, method) for route in member_facility_router.routes for method in (route.methods or [])}
    assert ("/bookings/{booking_id}/title", "PATCH") in routes
    assert ("/booking-series/{series_id}/title", "PATCH") in routes


def _list_item(booking_id, user_id, title: str) -> MemberBrowseBookingResult:
    return MemberBrowseBookingResult(
        id=booking_id,
        title=title,
        user_id=user_id,
        booking_type="one_time",
        start_at=datetime(2026, 5, 1, 10, 0, tzinfo=timezone.utc),
        end_at=datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc),
        status="confirmed",
    )
