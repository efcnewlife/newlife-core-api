"""
Database-backed One-time Priority override confirmation checks (EFC-258).

Proves atomic commit/rollback and room-lock serialization against real PostgreSQL;
stub tests cannot. Opt-in: needs a migrated database with at least two rooms, two users,
and an Active Priority Ministry with a steward.

    PORTAL_DB_INTEGRATION=1 uv run pytest tests/integration -v
"""

import asyncio
import os
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from portal.application.facility.booking_draft_service import BookingDraftService
from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingDraftLineCommand, BookingRoomLineCommand, CreateBookingCommand, CreateBookingDraftCommand
from portal.domain.facility.constants import BookingErrorCode, BookingSlotStatus, BookingStatus
from portal.exceptions.responses import ConflictErrorException
from portal.infrastructure.persistence.repositories.facility.booking_draft_repository import BookingDraftRepository
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.transaction_hooks import SessionTransactionHooks
from portal.libs.database import Session
from tests.fixtures.facility.factories import make_preview_quote_result
from tests.fixtures.facility.stubs import StubFileService, StubPricingService, StubRecurringOverrideNotifier, StubRoomSlotTemplateRepository
from tests.fixtures.system.stubs import StubSettingService

pytestmark = pytest.mark.skipif(os.getenv("PORTAL_DB_INTEGRATION") != "1", reason="set PORTAL_DB_INTEGRATION=1 to run against a migrated database")

SECRET = b"db-review-secret"


def _session() -> Session:
    return Session(use_poll=False)


def _as_user(monkeypatch, user_id: UUID):
    ctx = type("UserCtx", (), {})()
    ctx.user_id = user_id
    ctx.username = "efc-258-it"
    monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: ctx)
    monkeypatch.setattr("portal.application.facility.booking_draft_service.get_user_context", lambda: ctx)


def _services(session: Session, notifier: StubRecurringOverrideNotifier) -> tuple[BookingService, BookingDraftService]:
    quote = make_preview_quote_result(quoted_amount=Decimal("100"))
    bookings = BookingRepository(session)
    ministries = MinistryRepository(session)
    drafts = BookingDraftRepository(session)
    blackouts = RoomBlackoutRepository(session)
    templates = StubRoomSlotTemplateRepository()
    booking_service = BookingService(
        bookings,
        StubPricingService(quote),
        ministries,
        blackouts,
        StubSettingService(),
        drafts,
        StubFileService(),
        templates,
        OverrideLogRepository(session),
        SessionTransactionHooks(session),
        notifier,
        review_secret=SECRET,
    )
    draft_service = BookingDraftService(
        drafts, bookings, blackouts, StubPricingService(quote), StubSettingService(), templates, ministries, review_secret=SECRET
    )
    return booking_service, draft_service


class _Fixture:
    rooms: list[UUID]
    renter_id: UUID
    other_user_id: UUID
    steward_id: UUID
    ministry_id: UUID
    start_at: datetime
    end_at: datetime


@pytest_asyncio.fixture
async def world():
    session = _session()
    fixture = _Fixture()
    ministry = await session.fetchrow(
        """
        SELECT m.id AS ministry_id, mm.user_id AS steward_id
        FROM org.ministry m JOIN org.ministry_member mm ON mm.ministry_id = m.id
        WHERE m.has_priority_booking AND m.status = 'active' AND NOT m.is_deleted AND mm.member_role IN ('primary', 'secondary')
        LIMIT 1
        """
    )
    if not ministry:
        await session.close()
        pytest.skip("No Active Priority Ministry with a steward in this database")
    fixture.ministry_id = ministry["ministry_id"]
    fixture.steward_id = ministry["steward_id"]
    users = await session.fetchvals('SELECT id FROM auth."user" WHERE id <> $1 ORDER BY id LIMIT 2', fixture.steward_id, raw=True)
    fixture.rooms = await session.fetchvals("SELECT id FROM facility.room WHERE NOT is_deleted ORDER BY id LIMIT 2", raw=True)
    if len(users) < 2 or len(fixture.rooms) < 2:
        await session.close()
        pytest.skip("Need two users and two rooms")
    fixture.renter_id, fixture.other_user_id = users
    day = datetime(2099, 1, 1, tzinfo=timezone.utc) + timedelta(days=random.randint(0, 3000))
    fixture.start_at = day.replace(hour=15)
    fixture.end_at = day.replace(hour=17)
    await session.close()
    yield fixture
    cleanup = _session()
    window = (fixture.start_at - timedelta(hours=12), fixture.end_at + timedelta(hours=12))
    booking_ids = await cleanup.fetchvals(
        "SELECT DISTINCT facility_booking_id FROM facility.booking_slot WHERE facility_id = ANY($1::uuid[]) AND start_at >= $2 AND start_at < $3",
        fixture.rooms,
        *window,
        raw=True,
    )
    if booking_ids:
        await cleanup.execute(
            "DELETE FROM facility.booking_override_log WHERE facility_booking_id = ANY($1::uuid[]) OR overridden_booking_id = ANY($1::uuid[])", booking_ids
        )
        await cleanup.execute("DELETE FROM facility.booking_slot WHERE facility_booking_id = ANY($1::uuid[])", booking_ids)
        await cleanup.execute("DELETE FROM facility.booking_room WHERE facility_booking_id = ANY($1::uuid[])", booking_ids)
        await cleanup.execute("DELETE FROM facility.booking WHERE id = ANY($1::uuid[])", booking_ids)
    await cleanup.execute(
        "DELETE FROM facility.booking_draft_line WHERE booking_draft_id IN (SELECT id FROM facility.booking_draft WHERE title = 'EFC-258 IT')"
    )
    await cleanup.execute("DELETE FROM facility.booking_draft WHERE title = 'EFC-258 IT'")
    await cleanup.commit()
    await cleanup.close()


async def _seed_rental(monkeypatch, fixture: _Fixture) -> UUID:
    """A committed future Rental Booking occupying both rooms."""
    session = _session()
    _as_user(monkeypatch, fixture.renter_id)
    booking_service, _ = _services(session, StubRecurringOverrideNotifier())
    result = await booking_service.create_booking(
        CreateBookingCommand(
            title="EFC-258 rental",
            start_at=fixture.start_at,
            end_at=fixture.end_at,
            rooms=[BookingRoomLineCommand(facility_id=room, sequence=index) for index, room in enumerate(fixture.rooms)],
            allow_priority_override=True,
        )
    )
    await session.commit()
    await session.close()
    return result.id


async def _reviewed_priority_create(monkeypatch, fixture: _Fixture, session: Session, notifier) -> tuple[UUID, UUID]:
    """Save and review the Draft in an earlier committed request, then confirm it inside ``session`` (left open)."""
    _as_user(monkeypatch, fixture.steward_id)
    draft_session = _session()
    _, draft_service = _services(draft_session, StubRecurringOverrideNotifier())
    draft = await draft_service.create_draft(
        CreateBookingDraftCommand(
            title="EFC-258 IT",
            ministry_id=fixture.ministry_id,
            lines=[BookingDraftLineCommand(facility_id=fixture.rooms[0], start_at=fixture.start_at, end_at=fixture.end_at)],
        )
    )
    await draft_session.commit()
    reviewed = await draft_service.get_draft(draft.id)
    await draft_session.close()
    assert reviewed.override_review_token
    assert {interval.facility_id for interval in reviewed.override_impacts[0].released_intervals} == set(fixture.rooms)

    booking_service, _ = _services(session, notifier)
    result = await booking_service.create_booking(
        CreateBookingCommand(
            start_at=fixture.start_at,
            end_at=fixture.end_at,
            ministry_id=fixture.ministry_id,
            rooms=[BookingRoomLineCommand(facility_id=fixture.rooms[0], sequence=0)],
            booking_draft_id=draft.id,
            allow_priority_override=True,
            override_review_token=reviewed.override_review_token,
        )
    )
    return result.id, draft.id


async def _state(booking_id: UUID) -> tuple[str, list[str]]:
    session = _session()
    status = await session.fetchval("SELECT status FROM facility.booking WHERE id = $1", booking_id)
    slots = await session.fetchvals("SELECT status FROM facility.booking_slot WHERE facility_booking_id = $1", booking_id, raw=True)
    await session.close()
    return status, sorted(slots)


@pytest.mark.asyncio
async def test_committed_override_releases_every_room_and_notifies_after_commit(monkeypatch, world):
    rental_id = await _seed_rental(monkeypatch, world)
    session = _session()
    notifier = StubRecurringOverrideNotifier()
    replacement_id, draft_id = await _reviewed_priority_create(monkeypatch, world, session, notifier)
    assert notifier.calls == []

    await session.commit()
    await session.close()

    assert await _state(rental_id) == (BookingStatus.OVERRIDDEN.value, [BookingSlotStatus.CANCELLED.value] * 2)
    assert (await _state(replacement_id))[0] == BookingStatus.CONFIRMED.value
    check = _session()
    logs = await check.fetch("SELECT facility_id FROM facility.booking_override_log WHERE overridden_booking_id = $1", rental_id, raw=True)
    draft_left = await check.fetchval("SELECT count(*) FROM facility.booking_draft WHERE id = $1", draft_id)
    await check.close()
    assert [row["facility_id"] for row in logs] == [world.rooms[0]]
    assert draft_left == 0
    assert [item.booking_id for item in notifier.calls[0].items] == [rental_id]


@pytest.mark.asyncio
async def test_rolled_back_override_leaves_target_draft_and_mail_untouched(monkeypatch, world):
    rental_id = await _seed_rental(monkeypatch, world)
    session = _session()
    notifier = StubRecurringOverrideNotifier()
    replacement_id, draft_id = await _reviewed_priority_create(monkeypatch, world, session, notifier)

    await session.rollback()
    await session.commit()
    await session.close()

    assert await _state(rental_id) == (BookingStatus.CONFIRMED.value, [BookingSlotStatus.CONFIRMED.value] * 2)
    assert await _state(replacement_id) == (None, [])
    check = _session()
    draft_left = await check.fetchval("SELECT count(*) FROM facility.booking_draft WHERE id = $1", draft_id)
    logs = await check.fetchval("SELECT count(*) FROM facility.booking_override_log WHERE overridden_booking_id = $1", rental_id)
    await check.close()
    assert draft_left == 1
    assert logs == 0
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_competing_creates_on_same_room_serialize(monkeypatch, world):
    def command():
        return CreateBookingCommand(
            title="EFC-258 race",
            start_at=world.start_at,
            end_at=world.end_at,
            rooms=[BookingRoomLineCommand(facility_id=world.rooms[0], sequence=0)],
            allow_priority_override=True,
        )

    first_session, second_session = _session(), _session()
    _as_user(monkeypatch, world.renter_id)
    first_service, _ = _services(first_session, StubRecurringOverrideNotifier())
    _as_user(monkeypatch, world.other_user_id)
    second_service, _ = _services(second_session, StubRecurringOverrideNotifier())

    await first_service.create_booking(command())
    racing = asyncio.create_task(second_service.create_booking(command()))
    await asyncio.sleep(0.5)
    assert not racing.done(), "second create must wait for the first transaction's room lock"

    await first_session.commit()
    with pytest.raises(ConflictErrorException) as exc_info:
        await racing
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    await second_session.rollback()
    await first_session.close()
    await second_session.close()
