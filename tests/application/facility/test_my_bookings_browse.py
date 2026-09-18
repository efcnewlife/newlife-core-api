"""Participant-scoped My Bookings browse tests."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from portal.application.content.results import FileGridItemResult
from portal.application.facility.commands import MemberBrowseQueryCommand
from portal.application.facility.mappers import member_browse_page_to_api, member_browse_query_to_command
from portal.application.facility.results import MemberBrowseBookingResult, MemberBrowseCardResult, MemberBrowsePageResult
from portal.domain.facility.constants import BookingStatus, BookingType, MyBookingsCardKind, MyBookingsSection
from portal.exceptions.responses import ForbiddenException
from portal.routers.apis.v1.facility import router as member_facility_router
from portal.serializers.apis.v1.facility import MemberBookingBrowseQuery
from tests.application.facility.test_booking_service import _booking_service, _user_ctx
from tests.fixtures.facility.stubs import StubBookingRepository, StubFileService, StubMinistryRepository

NOW = datetime(2026, 9, 18, 16, 0, tzinfo=timezone.utc)


def _browse_row(
    *,
    user_id,
    start_at: datetime,
    end_at: datetime | None = None,
    status: str = BookingStatus.CONFIRMED.value,
    booking_type: str = BookingType.ONE_TIME.value,
    series_id=None,
    series_title: str | None = None,
    ministry_id=None,
    facility_id=None,
    title: str = "Choir practice",
    payment_hold_expires_at: datetime | None = None,
) -> MemberBrowseBookingResult:
    room_id = facility_id or uuid4()
    return MemberBrowseBookingResult(
        id=uuid4(),
        title=title,
        user_id=user_id,
        facility_id=room_id,
        facility_name="Gym",
        booking_type=booking_type,
        series_id=series_id,
        series_title=series_title,
        ministry_id=ministry_id,
        start_at=start_at,
        end_at=end_at or (start_at + timedelta(hours=2)),
        status=status,
        quoted_amount=None,
        currency="CAD",
        payment_hold_expires_at=payment_hold_expires_at,
    )


def _service(monkeypatch, *, user_id, rows, owned_ministry_ids=None, file_service=None):
    _user_ctx(monkeypatch, user_id=user_id)
    booking_stub = StubBookingRepository(participant_bookings=rows)
    ministry_stub = StubMinistryRepository(owned_active_ids=owned_ministry_ids or [])
    return _booking_service(booking_stub, ministry_stub=ministry_stub, file_service=file_service or StubFileService())


@pytest.mark.asyncio
async def test_browse_requires_authenticated_user(monkeypatch):
    monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: None)
    service = _booking_service(StubBookingRepository())
    with pytest.raises(ForbiddenException):
        await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)


@pytest.mark.asyncio
async def test_booker_browses_own_upcoming_one_time_booking(monkeypatch):
    owner_id = uuid4()
    row = _browse_row(user_id=owner_id, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc), title="Choir practice")
    service = _service(monkeypatch, user_id=owner_id, rows=[row])
    result = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert result.total == 1
    assert result.section == MyBookingsSection.UPCOMING.value
    card = result.items[0]
    assert card.kind == MyBookingsCardKind.ONE_TIME.value
    assert card.is_booker is True
    assert card.is_view_only is False
    assert card.booking is not None
    assert card.booking.id == row.id
    assert card.booking.title == "Choir practice"
    assert card.photo_urls == []


@pytest.mark.asyncio
async def test_current_ministry_member_browses_ministry_booking_as_view_only(monkeypatch):
    member_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    row = _browse_row(user_id=booker_id, ministry_id=ministry_id, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc), title="Ministry rehearsal")
    service = _service(monkeypatch, user_id=member_id, rows=[row], owned_ministry_ids=[ministry_id])
    result = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert result.total == 1
    assert result.items[0].is_booker is False
    assert result.items[0].is_view_only is True
    assert result.items[0].booking is not None
    assert result.items[0].booking.title == "Ministry rehearsal"


@pytest.mark.asyncio
async def test_former_ministry_member_does_not_see_ministry_booking(monkeypatch):
    former_id = uuid4()
    booker_id = uuid4()
    ministry_id = uuid4()
    row = _browse_row(user_id=booker_id, ministry_id=ministry_id, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc))
    service = _service(monkeypatch, user_id=former_id, rows=[row], owned_ministry_ids=[])
    result = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert result.total == 0
    assert result.items == []


@pytest.mark.asyncio
async def test_unrelated_user_does_not_see_another_bookers_booking(monkeypatch):
    viewer_id = uuid4()
    row = _browse_row(user_id=uuid4(), start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc))
    service = _service(monkeypatch, user_id=viewer_id, rows=[row])
    result = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert result.total == 0


@pytest.mark.asyncio
async def test_browse_classifies_upcoming_past_overridden_and_expired_hold(monkeypatch):
    owner_id = uuid4()
    upcoming = _browse_row(user_id=owner_id, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc), title="Upcoming")
    past = _browse_row(user_id=owner_id, start_at=datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc), title="Past")
    overridden = _browse_row(
        user_id=owner_id, start_at=datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc), status=BookingStatus.OVERRIDDEN.value, title="Overridden"
    )
    cancelled = _browse_row(
        user_id=owner_id, start_at=datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc), status=BookingStatus.CANCELLED.value, title="Cancelled"
    )
    expired_hold = _browse_row(
        user_id=owner_id,
        start_at=datetime(2026, 10, 4, 14, 0, tzinfo=timezone.utc),
        status=BookingStatus.PENDING_PAYMENT.value,
        payment_hold_expires_at=NOW - timedelta(hours=1),
        title="Expired hold",
    )
    service = _service(monkeypatch, user_id=owner_id, rows=[upcoming, past, overridden, cancelled, expired_hold])

    upcoming_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert [card.booking.title for card in upcoming_page.items if card.booking] == ["Upcoming"]

    past_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.PAST), now=NOW)
    assert [card.booking.title for card in past_page.items if card.booking] == ["Past"]

    overridden_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.OVERRIDDEN), now=NOW)
    assert [card.booking.title for card in overridden_page.items if card.booking] == ["Overridden"]

    cancelled_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.CANCELLED_OR_EXPIRED), now=NOW)
    assert {card.booking.title for card in cancelled_page.items if card.booking} == {"Cancelled", "Expired hold"}


@pytest.mark.asyncio
async def test_browse_paginates_cards_without_silent_100_cap(monkeypatch):
    owner_id = uuid4()
    rows = [
        _browse_row(user_id=owner_id, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc) + timedelta(days=index), title=f"Booking {index:02d}")
        for index in range(5)
    ]
    service = _service(monkeypatch, user_id=owner_id, rows=rows)
    first = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING, page=0, page_size=2), now=NOW)
    second = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING, page=1, page_size=2), now=NOW)
    third = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING, page=2, page_size=2), now=NOW)
    assert first.total == 5
    assert [card.booking.title for card in first.items if card.booking] == ["Booking 00", "Booking 01"]
    assert [card.booking.title for card in second.items if card.booking] == ["Booking 02", "Booking 03"]
    assert [card.booking.title for card in third.items if card.booking] == ["Booking 04"]

    many = [
        _browse_row(user_id=owner_id, start_at=datetime(2026, 11, 1, 14, 0, tzinfo=timezone.utc) + timedelta(minutes=index), title=f"Extra {index:03d}")
        for index in range(101)
    ]
    many_service = _service(monkeypatch, user_id=owner_id, rows=many)
    page_zero = await many_service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING, page=0, page_size=50), now=NOW)
    page_two = await many_service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING, page=2, page_size=50), now=NOW)
    assert page_zero.total == 101
    assert len(page_zero.items) == 50
    assert len(page_two.items) == 1
    assert page_two.items[0].booking is not None
    assert page_two.items[0].booking.title == "Extra 100"


@pytest.mark.asyncio
async def test_series_projects_only_section_occurrences_and_keeps_series_link(monkeypatch):
    owner_id = uuid4()
    series_id = uuid4()
    upcoming_one = _browse_row(
        user_id=owner_id,
        booking_type=BookingType.RECURRING.value,
        series_id=series_id,
        series_title="Weekly choir",
        start_at=datetime(2026, 10, 8, 14, 0, tzinfo=timezone.utc),
        title="Week 3",
    )
    upcoming_two = _browse_row(
        user_id=owner_id,
        booking_type=BookingType.RECURRING.value,
        series_id=series_id,
        series_title="Weekly choir",
        start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc),
        title="Week 2",
    )
    past = _browse_row(
        user_id=owner_id,
        booking_type=BookingType.RECURRING.value,
        series_id=series_id,
        series_title="Weekly choir",
        start_at=datetime(2026, 8, 1, 14, 0, tzinfo=timezone.utc),
        title="Week 1",
    )
    overridden = _browse_row(
        user_id=owner_id,
        booking_type=BookingType.RECURRING.value,
        series_id=series_id,
        series_title="Weekly choir",
        start_at=datetime(2026, 10, 15, 14, 0, tzinfo=timezone.utc),
        status=BookingStatus.OVERRIDDEN.value,
        title="Week 4 overridden",
    )
    service = _service(monkeypatch, user_id=owner_id, rows=[upcoming_one, upcoming_two, past, overridden])

    upcoming_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    assert upcoming_page.total == 1
    series_card = upcoming_page.items[0]
    assert series_card.kind == MyBookingsCardKind.SERIES.value
    assert series_card.series_id == series_id
    assert series_card.series_title == "Weekly choir"
    assert [item.title for item in series_card.occurrences] == ["Week 2", "Week 3"]

    past_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.PAST), now=NOW)
    assert past_page.items[0].series_id == series_id
    assert [item.title for item in past_page.items[0].occurrences] == ["Week 1"]

    overridden_page = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.OVERRIDDEN), now=NOW)
    assert overridden_page.items[0].series_id == series_id
    assert [item.title for item in overridden_page.items[0].occurrences] == ["Week 4 overridden"]


@pytest.mark.asyncio
async def test_browse_card_uses_primary_facility_gallery_or_empty_fallback(monkeypatch):
    owner_id = uuid4()
    room_with_photos = uuid4()
    room_without_photos = uuid4()
    with_photos = _browse_row(user_id=owner_id, facility_id=room_with_photos, start_at=datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc), title="Has photos")
    without_photos = _browse_row(
        user_id=owner_id, facility_id=room_without_photos, start_at=datetime(2026, 10, 2, 14, 0, tzinfo=timezone.utc), title="No photos"
    )
    file_service = StubFileService(
        files_by_resource={
            room_with_photos: [
                FileGridItemResult(id=uuid4(), original_name="a.jpg", key="a", storage="s3", bucket="b", region="ca-central-1", url="https://cdn.example/a.jpg")
            ]
        }
    )
    service = _service(monkeypatch, user_id=owner_id, rows=[with_photos, without_photos], file_service=file_service)
    result = await service.browse_my_bookings(MemberBrowseQueryCommand(section=MyBookingsSection.UPCOMING), now=NOW)
    by_title = {card.booking.title: card for card in result.items if card.booking}
    assert by_title["Has photos"].photo_urls == ["https://cdn.example/a.jpg"]
    assert by_title["No photos"].photo_urls == []


def test_browse_query_requires_section():
    with pytest.raises(ValidationError):
        MemberBookingBrowseQuery()
    command = member_browse_query_to_command(MemberBookingBrowseQuery(section=MyBookingsSection.UPCOMING, page=1, page_size=20))
    assert command.section == MyBookingsSection.UPCOMING
    assert command.page == 1
    assert command.page_size == 20


def test_browse_page_api_uses_camel_case_and_view_only_flags():
    booking_id = uuid4()
    facility_id = uuid4()
    start_at = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    end_at = datetime(2026, 10, 1, 16, 0, tzinfo=timezone.utc)
    page = MemberBrowsePageResult(
        page=0,
        page_size=20,
        total=1,
        section=MyBookingsSection.UPCOMING.value,
        items=[
            MemberBrowseCardResult(
                kind=MyBookingsCardKind.ONE_TIME.value,
                is_booker=False,
                is_view_only=True,
                photo_urls=["https://cdn.example/a.jpg"],
                booking=MemberBrowseBookingResult(
                    id=booking_id,
                    title="Ministry rehearsal",
                    user_id=uuid4(),
                    facility_id=facility_id,
                    facility_name="Gym",
                    booking_type=BookingType.ONE_TIME.value,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingStatus.CONFIRMED.value,
                ),
            )
        ],
    )
    dumped = member_browse_page_to_api(page).model_dump(by_alias=True)
    assert dumped["pageSize"] == 20
    assert dumped["section"] == "upcoming"
    card = dumped["items"][0]
    assert card["isBooker"] is False
    assert card["isViewOnly"] is True
    assert card["photoUrls"] == ["https://cdn.example/a.jpg"]
    assert card["booking"]["facilityId"] == facility_id
    assert card["booking"]["startAt"] == start_at


def test_member_browse_route_exists():
    routes = {(route.path, method) for route in member_facility_router.routes for method in (route.methods or [])}
    assert ("/bookings/mine", "GET") in routes
