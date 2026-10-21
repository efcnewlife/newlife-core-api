"""
Owned One-time Draft review exposes confirmability, redacted conflicts, whole-Booking override impact and a review token (EFC-258).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from portal.application.facility.booking_draft_service import BookingDraftService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingDraftLineCommand, BookingRoomLineCommand, UpdateBookingDraftCommand
from portal.application.facility.results import (
    BookingDraftDetailResult,
    BookingDraftStoredLineResult,
    OverrideReleasedIntervalResult,
    RecurringOccupyingBookingResult,
)
from portal.application.org.results import MinistryMemberResult
from portal.domain.org.constants import MinistryMemberRole
from portal.exceptions.responses import ConflictErrorException, NotFoundException
from tests.fixtures.facility.factories import make_create_booking_command, make_ministry_detail, make_preview_quote_result
from tests.fixtures.facility.stubs import (
    StubBookingDraftRepository,
    StubBookingRepository,
    StubFileService,
    StubMinistryRepository,
    StubOverrideLogRepository,
    StubPricingService,
    StubRecurringOverrideNotifier,
    StubRoomBlackoutRepository,
    StubRoomSlotTemplateRepository,
    StubTransactionHooks,
)
from tests.fixtures.system.stubs import StubSettingService

SECRET = b"review-secret"
NOW = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
START = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
END = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)


def _login(monkeypatch, user_id):
    ctx = type("UserCtx", (), {})()
    ctx.user_id = user_id
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: ctx)
    monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: ctx)


def _occupant(room, *, ministry_id=None, start=START, ministry_name=None):
    return RecurringOccupyingBookingResult(
        booking_id=uuid4(),
        user_id=uuid4(),
        ministry_id=ministry_id,
        ministry_name=ministry_name,
        facility_ids=[room],
        start_at=start,
        end_at=END,
        booker_display_name="Rita Renter",
        booker_email="rita@example.com",
    )


class _World:
    def __init__(self, *, user_id, ministry_id=None, is_priority=True, stewards=None, occupants=(), members=None, blackout=False):
        ministries = {}
        if ministry_id:
            ministries[ministry_id] = make_ministry_detail(ministry_id).model_copy(update={"has_priority_booking": is_priority})
        self.bookings = StubBookingRepository(occupying_bookings=list(occupants))
        self.ministries = StubMinistryRepository(
            ministry_by_id=ministries, booking_member_user_ids=stewards if stewards is not None else {user_id}, members_by_ministry=members or {}
        )
        self.drafts = StubBookingDraftRepository()
        self.hooks = StubTransactionHooks()
        self.notifier = StubRecurringOverrideNotifier()
        self.blackouts = StubRoomBlackoutRepository(has_overlap=blackout)
        quote = make_preview_quote_result(quoted_amount=Decimal("100"))
        self.draft_service = BookingDraftService(
            self.drafts,
            self.bookings,
            self.blackouts,
            StubPricingService(quote),
            StubSettingService(),
            StubRoomSlotTemplateRepository(),
            self.ministries,
            now_utc=lambda: NOW,
            review_secret=SECRET,
        )
        self.booking_service = BookingService(
            self.bookings,
            StubPricingService(quote),
            self.ministries,
            self.blackouts,
            StubSettingService(),
            self.drafts,
            StubFileService(),
            StubRoomSlotTemplateRepository(),
            StubOverrideLogRepository(),
            self.hooks,
            self.notifier,
            now_utc=lambda: NOW,
            review_secret=SECRET,
        )

    def store_draft(self, *, user_id, ministry_id, rooms):
        draft_id = uuid4()
        self.drafts.draft_by_id[draft_id] = BookingDraftDetailResult(
            id=draft_id,
            user_id=user_id,
            title="Retreat",
            date=START.date(),
            ministry_id=ministry_id,
            lines=[BookingDraftStoredLineResult(facility_id=room, start_at=START, end_at=END, sequence=index) for index, room in enumerate(rooms)],
        )
        return draft_id


@pytest.mark.asyncio
async def test_priority_draft_reviews_whole_booking_impact_without_side_effects(monkeypatch):
    user_id, ministry_id, room, elsewhere = uuid4(), uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    target = _occupant(room)
    world = _World(user_id=user_id, ministry_id=ministry_id, occupants=[target])
    world.bookings.live_slot_intervals[target.booking_id] = [
        OverrideReleasedIntervalResult(facility_id=room, start_at=START, end_at=END),
        OverrideReleasedIntervalResult(facility_id=elsewhere, start_at=START + timedelta(hours=4), end_at=END + timedelta(hours=4)),
    ]
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room])

    result = await world.draft_service.get_draft(draft_id)

    assert result.is_confirmable is True
    assert result.conflicts == []
    assert [impact.booking_id for impact in result.override_impacts] == [target.booking_id]
    assert {interval.facility_id for interval in result.override_impacts[0].released_intervals} == {room, elsewhere}
    assert result.override_review_token
    assert world.bookings.override_calls == []
    assert world.bookings.insert_calls == []
    assert world.hooks.callbacks == []


@pytest.mark.asyncio
async def test_reviewed_draft_token_confirms_and_consumes_draft(monkeypatch):
    user_id, ministry_id, room = uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    target = _occupant(room)
    world = _World(user_id=user_id, ministry_id=ministry_id, occupants=[target])
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room])
    reviewed = await world.draft_service.get_draft(draft_id)

    command = make_create_booking_command(facility_id=room, start_at=START, end_at=END, ministry_id=ministry_id, booking_draft_id=draft_id)
    command.allow_priority_override = True
    command.override_review_token = reviewed.override_review_token
    await world.booking_service.create_booking(command)

    assert [call["booking_id"] for call in world.bookings.override_calls] == [target.booking_id]
    assert world.drafts.delete_draft_calls == [draft_id]


@pytest.mark.asyncio
async def test_editing_draft_reevaluates_without_reserving(monkeypatch):
    user_id, ministry_id, room, other_room = uuid4(), uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    world = _World(user_id=user_id, ministry_id=ministry_id, occupants=[_occupant(other_room)])
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room])
    first = await world.draft_service.get_draft(draft_id)
    assert first.override_impacts == [] and first.override_review_token is None

    updated = await world.draft_service.update_draft(
        draft_id,
        UpdateBookingDraftCommand(
            title="Retreat", ministry_id=ministry_id, lines=[BookingDraftLineCommand(facility_id=other_room, start_at=START, end_at=END)]
        ),
    )

    assert len(updated.override_impacts) == 1
    assert updated.override_review_token
    assert world.bookings.override_calls == [] and world.hooks.callbacks == []


@pytest.mark.asyncio
async def test_personal_draft_redacts_ministry_occupancy(monkeypatch):
    user_id, room = uuid4(), uuid4()
    _login(monkeypatch, user_id)
    world = _World(user_id=user_id, occupants=[_occupant(room, ministry_id=uuid4(), ministry_name="Choir"), _occupant(room)])
    draft_id = world.store_draft(user_id=user_id, ministry_id=None, rooms=[room])

    result = await world.draft_service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert [conflict.model_dump(exclude_none=True) for conflict in result.conflicts] == [
        {"facility_id": room, "start_at": START, "end_at": END, "kind": "occupancy"}
    ]
    assert result.override_impacts == [] and result.override_review_token is None


@pytest.mark.asyncio
async def test_lost_stewardship_projects_draft_as_personal_and_blocks_confirmation(monkeypatch):
    user_id, ministry_id, room = uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    world = _World(user_id=user_id, ministry_id=ministry_id, stewards=set(), occupants=[_occupant(room)])
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room])

    result = await world.draft_service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert result.override_impacts == [] and result.override_review_token is None
    assert all(conflict.contact_email is None for conflict in result.conflicts)


@pytest.mark.asyncio
async def test_lost_stewardship_without_conflicts_is_not_confirmable(monkeypatch):
    user_id, ministry_id, room = uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    world = _World(user_id=user_id, ministry_id=ministry_id, stewards=set())
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room])
    result = await world.draft_service.get_draft(draft_id)
    assert result.is_confirmable is False


@pytest.mark.asyncio
async def test_priority_draft_with_ministry_occupancy_lists_contact_and_issues_no_token(monkeypatch):
    user_id, ministry_id, other_ministry, room_a, room_b = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    _login(monkeypatch, user_id)
    members = {other_ministry: [MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat", email="pat@efc.org")]}
    world = _World(
        user_id=user_id,
        ministry_id=ministry_id,
        occupants=[_occupant(room_a), _occupant(room_b, ministry_id=other_ministry, ministry_name="Choir")],
        members=members,
    )
    draft_id = world.store_draft(user_id=user_id, ministry_id=ministry_id, rooms=[room_a, room_b])

    result = await world.draft_service.get_draft(draft_id)

    assert result.is_confirmable is False
    assert len(result.override_impacts) == 1
    assert result.override_review_token is None
    assert [(c.kind, c.ministry_name, c.contact_display_name, c.contact_email) for c in result.conflicts] == [("ministry", "Choir", "Pat", "pat@efc.org")]


@pytest.mark.asyncio
async def test_blackout_line_is_a_closed_conflict(monkeypatch):
    user_id, room = uuid4(), uuid4()
    _login(monkeypatch, user_id)
    world = _World(user_id=user_id, blackout=True)
    draft_id = world.store_draft(user_id=user_id, ministry_id=None, rooms=[room])
    result = await world.draft_service.get_draft(draft_id)
    assert result.is_confirmable is False
    assert [conflict.kind for conflict in result.conflicts] == ["blackout"]
    assert result.lines[0].is_available is False


@pytest.mark.asyncio
async def test_other_users_draft_is_not_found(monkeypatch):
    owner, intruder, room = uuid4(), uuid4(), uuid4()
    _login(monkeypatch, intruder)
    world = _World(user_id=intruder)
    draft_id = world.store_draft(user_id=owner, ministry_id=None, rooms=[room])
    with pytest.raises(NotFoundException):
        await world.draft_service.get_draft(draft_id)


@pytest.mark.asyncio
async def test_token_from_other_booker_is_stale_for_create(monkeypatch):
    owner, other, ministry_id, room = uuid4(), uuid4(), uuid4(), uuid4()
    _login(monkeypatch, owner)
    world = _World(user_id=owner, ministry_id=ministry_id, stewards={owner, other}, occupants=[_occupant(room)])
    draft_id = world.store_draft(user_id=owner, ministry_id=ministry_id, rooms=[room])
    token = (await world.draft_service.get_draft(draft_id)).override_review_token

    world.booking_service._user_ctx.user_id = other
    command = make_create_booking_command(facility_id=room, start_at=START, end_at=END, ministry_id=ministry_id)
    command.rooms = [BookingRoomLineCommand(facility_id=room, sequence=0)]
    command.allow_priority_override = True
    command.override_review_token = token
    with pytest.raises(ConflictErrorException) as exc_info:
        await world.booking_service.create_booking(command)
    assert exc_info.value.error_code == "FACILITY_BOOKING_OVERRIDE_REVIEW_STALE"
    assert world.bookings.override_calls == []
