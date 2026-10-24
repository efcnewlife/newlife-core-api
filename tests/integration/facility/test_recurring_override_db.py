"""
Database-backed Recurring Priority override confirmation checks (EFC-259).

Proves multi-occurrence atomic commit/rollback, exclusions, stale-impact re-review and
room-lock serialization against real PostgreSQL. Opt-in: needs a migrated database with
at least one room, two users, and an Active Priority Ministry with a steward.

    PORTAL_DB_INTEGRATION=1 uv run pytest tests/integration -v
"""

import asyncio
import os
import random
from datetime import date, time, timedelta, timezone
from decimal import Decimal
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest
import pytest_asyncio

from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingRoomLineCommand, CreateBookingCommand, CreateRecurringSeriesDraftCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.recurring_series_draft_service import RecurringSeriesDraftService
from portal.domain.facility.constants import BookingErrorCode, BookingSlotStatus, BookingStatus
from portal.domain.facility.recurring import localize_wall_time
from portal.exceptions.responses import ConflictErrorException
from portal.infrastructure.persistence.repositories.facility.booking_draft_repository import BookingDraftRepository
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.infrastructure.persistence.repositories.facility.recurring_booking_repository import RecurringBookingRepository
from portal.infrastructure.persistence.repositories.facility.recurring_series_draft_repository import RecurringSeriesDraftRepository
from portal.infrastructure.persistence.repositories.facility.room_blackout_repository import RoomBlackoutRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository
from portal.infrastructure.persistence.transaction_hooks import SessionTransactionHooks
from portal.libs.database import Session
from tests.fixtures.facility.factories import make_preview_quote_result
from tests.fixtures.facility.stubs import (
    StubFileService,
    StubPricingService,
    StubRecurringOverrideNotifier,
    StubRoomSlotTemplateRepository,
    StubUserReadService,
)
from tests.fixtures.system.stubs import StubSettingService

pytestmark = pytest.mark.skipif(os.getenv("PORTAL_DB_INTEGRATION") != "1", reason="set PORTAL_DB_INTEGRATION=1 to run against a migrated database")

SECRET = b"db-recurring-review-secret"
MARKER = "EFC-259 IT"
WEEKS = 6
TORONTO = ZoneInfo("America/Toronto")


def _session() -> Session:
    return Session(use_poll=False)


def _as_user(monkeypatch, user_id: UUID):
    ctx = type("UserCtx", (), {})()
    ctx.user_id = user_id
    ctx.email = "efc-259-it@efcnewlife.org"
    ctx.username = "efc-259-it"
    for module in ("booking_service", "recurring_booking_service", "recurring_series_draft_service"):
        monkeypatch.setattr(f"portal.application.facility.{module}.get_user_context", lambda: ctx)


def _settings() -> StubSettingService:
    return StubSettingService(max_booking_lines=10, test_window_override=True)


def _booking_service(session: Session) -> BookingService:
    return BookingService(
        BookingRepository(session),
        StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
        MinistryRepository(session),
        RoomBlackoutRepository(session),
        _settings(),
        BookingDraftRepository(session),
        StubFileService(),
        StubRoomSlotTemplateRepository(),
        OverrideLogRepository(session),
        SessionTransactionHooks(session),
        review_secret=SECRET,
    )


def _draft_service(session: Session, notifier: StubRecurringOverrideNotifier) -> RecurringSeriesDraftService:
    recurring = RecurringBookingService(
        series_repository=RecurringBookingRepository(session),
        booking_repository=BookingRepository(session),
        pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
        ministry_repository=MinistryRepository(session),
        room_blackout_repository=RoomBlackoutRepository(session),
        setting_service=_settings(),
        user_read_service=StubUserReadService(email="efc-259-it@efcnewlife.org"),
        override_log_repository=OverrideLogRepository(session),
        room_slot_template_repository=StubRoomSlotTemplateRepository(),
        transaction_hooks=SessionTransactionHooks(session),
        override_notifier=notifier,
        review_secret=SECRET,
    )
    return RecurringSeriesDraftService(RecurringSeriesDraftRepository(session), recurring)


class _Fixture:
    room_id: UUID
    renter_id: UUID
    other_user_id: UUID
    steward_id: UUID
    ministry_id: UUID
    dates: list[date]


def _interval(occurrence_date: date):
    start = localize_wall_time(occurrence_date, time(10, 0), TORONTO).astimezone(timezone.utc)
    end = localize_wall_time(occurrence_date, time(12, 0), TORONTO).astimezone(timezone.utc)
    return start, end


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
    rooms = await session.fetchvals("SELECT id FROM facility.room WHERE NOT is_deleted ORDER BY id LIMIT 1", raw=True)
    await session.close()
    if len(users) < 2 or not rooms:
        pytest.skip("Need two users and one room")
    fixture.renter_id, fixture.other_user_id = users
    fixture.room_id = rooms[0]
    first = date(random.randint(2200, 2800), 2, 1)
    first += timedelta(days=(1 - first.weekday()) % 7)
    fixture.dates = [first + timedelta(weeks=index) for index in range(WEEKS)]
    yield fixture

    cleanup = _session()
    window_start, _ = _interval(fixture.dates[0])
    _, window_end = _interval(fixture.dates[-1])
    booking_ids = await cleanup.fetchvals(
        "SELECT DISTINCT facility_booking_id FROM facility.booking_slot WHERE facility_id = $1 AND start_at >= $2 AND start_at < $3",
        fixture.room_id,
        window_start - timedelta(hours=1),
        window_end + timedelta(hours=1),
        raw=True,
    )
    if booking_ids:
        await cleanup.execute(
            "DELETE FROM facility.booking_override_log WHERE facility_booking_id = ANY($1::uuid[]) OR overridden_booking_id = ANY($1::uuid[])", booking_ids
        )
        await cleanup.execute("DELETE FROM facility.booking_slot WHERE facility_booking_id = ANY($1::uuid[])", booking_ids)
        await cleanup.execute("DELETE FROM facility.booking_room WHERE facility_booking_id = ANY($1::uuid[])", booking_ids)
        await cleanup.execute("DELETE FROM facility.booking WHERE id = ANY($1::uuid[])", booking_ids)
    await cleanup.execute("DELETE FROM facility.booking_series WHERE title = $1", MARKER)
    await cleanup.execute(
        "DELETE FROM facility.booking_series_draft_room WHERE series_draft_id IN (SELECT id FROM facility.booking_series_draft WHERE title = $1)", MARKER
    )
    await cleanup.execute("DELETE FROM facility.booking_series_draft WHERE title = $1", MARKER)
    await cleanup.commit()
    await cleanup.close()


async def _seed_rental(monkeypatch, fixture: _Fixture, occurrence_date: date) -> UUID:
    """A committed future Personal One-time Rental on one Series occurrence."""
    session = _session()
    _as_user(monkeypatch, fixture.renter_id)
    start_at, end_at = _interval(occurrence_date)
    result = await _booking_service(session).create_booking(
        CreateBookingCommand(title="EFC-259 rental", start_at=start_at, end_at=end_at, rooms=[BookingRoomLineCommand(facility_id=fixture.room_id, sequence=0)])
    )
    await session.commit()
    await session.close()
    return result.id


async def _saved_draft(monkeypatch, fixture: _Fixture, excluded_dates=()) -> UUID:
    _as_user(monkeypatch, fixture.steward_id)
    session = _session()
    draft = await _draft_service(session, StubRecurringOverrideNotifier()).create_draft(
        CreateRecurringSeriesDraftCommand(
            title=MARKER,
            ministry_id=fixture.ministry_id,
            first_occurrence_date=fixture.dates[0],
            last_occurrence_date=fixture.dates[-1],
            local_start_time=time(10, 0),
            local_end_time=time(12, 0),
            rooms=[BookingRoomLineCommand(facility_id=fixture.room_id, sequence=0)],
            excluded_dates=list(excluded_dates),
        )
    )
    await session.commit()
    await session.close()
    return draft.id


async def _review(monkeypatch, fixture: _Fixture, draft_id: UUID):
    _as_user(monkeypatch, fixture.steward_id)
    session = _session()
    reviewed = await _draft_service(session, StubRecurringOverrideNotifier()).get_draft(draft_id)
    await session.close()
    return reviewed


async def _state(booking_id: UUID) -> tuple[str, list[str]]:
    session = _session()
    status = await session.fetchval("SELECT status FROM facility.booking WHERE id = $1", booking_id)
    slots = await session.fetchvals("SELECT status FROM facility.booking_slot WHERE facility_booking_id = $1", booking_id, raw=True)
    await session.close()
    return status, sorted(slots)


async def _count(sql: str, *args) -> int:
    session = _session()
    value = await session.fetchval(sql, *args)
    await session.close()
    return value


@pytest.mark.asyncio
async def test_committed_series_displaces_only_reviewed_remaining_occurrences_and_mails_after_commit(monkeypatch, world):
    displaced_id = await _seed_rental(monkeypatch, world, world.dates[1])
    excluded_id = await _seed_rental(monkeypatch, world, world.dates[2])
    draft_id = await _saved_draft(monkeypatch, world, excluded_dates=[world.dates[2]])
    reviewed = await _review(monkeypatch, world, draft_id)
    assert [impact.booking_id for impact in reviewed.override_impacts] == [displaced_id]

    session = _session()
    notifier = StubRecurringOverrideNotifier()
    _as_user(monkeypatch, world.steward_id)
    series = await _draft_service(session, notifier).confirm_draft(draft_id, override_review_token=reviewed.override_review_token)
    assert notifier.calls == []
    await session.commit()
    await session.close()

    assert series.occurrence_count == WEEKS - 1
    assert await _state(displaced_id) == (BookingStatus.OVERRIDDEN.value, [BookingSlotStatus.CANCELLED.value])
    assert await _state(excluded_id) == (BookingStatus.CONFIRMED.value, [BookingSlotStatus.CONFIRMED.value])
    assert await _count("SELECT count(*) FROM facility.booking WHERE series_id = $1", series.id) == WEEKS - 1
    assert await _count("SELECT count(*) FROM facility.booking_override_log WHERE overridden_booking_id = $1", displaced_id) == 1
    assert await _count("SELECT count(*) FROM facility.booking_series_draft WHERE id = $1", draft_id) == 0
    assert [item.booking_id for item in notifier.calls[0].items] == [displaced_id]


@pytest.mark.asyncio
async def test_rolled_back_series_confirmation_leaves_targets_draft_and_mail_untouched(monkeypatch, world):
    first_id = await _seed_rental(monkeypatch, world, world.dates[1])
    second_id = await _seed_rental(monkeypatch, world, world.dates[3])
    draft_id = await _saved_draft(monkeypatch, world)
    reviewed = await _review(monkeypatch, world, draft_id)

    session = _session()
    notifier = StubRecurringOverrideNotifier()
    _as_user(monkeypatch, world.steward_id)
    series = await _draft_service(session, notifier).confirm_draft(draft_id, override_review_token=reviewed.override_review_token)
    await session.rollback()
    await session.commit()
    await session.close()

    for rental_id in (first_id, second_id):
        assert await _state(rental_id) == (BookingStatus.CONFIRMED.value, [BookingSlotStatus.CONFIRMED.value])
    assert await _count("SELECT count(*) FROM facility.booking_series WHERE id = $1", series.id) == 0
    assert await _count("SELECT count(*) FROM facility.booking_series_draft WHERE id = $1", draft_id) == 1
    assert notifier.calls == []


@pytest.mark.asyncio
async def test_new_target_after_review_is_stale_until_re_reviewed(monkeypatch, world):
    await _seed_rental(monkeypatch, world, world.dates[1])
    draft_id = await _saved_draft(monkeypatch, world)
    stale = await _review(monkeypatch, world, draft_id)
    late_id = await _seed_rental(monkeypatch, world, world.dates[4])

    session = _session()
    _as_user(monkeypatch, world.steward_id)
    with pytest.raises(ConflictErrorException) as exc_info:
        await _draft_service(session, StubRecurringOverrideNotifier()).confirm_draft(draft_id, override_review_token=stale.override_review_token)
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    await session.rollback()
    await session.close()
    assert await _state(late_id) == (BookingStatus.CONFIRMED.value, [BookingSlotStatus.CONFIRMED.value])

    fresh = await _review(monkeypatch, world, draft_id)
    session = _session()
    _as_user(monkeypatch, world.steward_id)
    await _draft_service(session, StubRecurringOverrideNotifier()).confirm_draft(draft_id, override_review_token=fresh.override_review_token)
    await session.commit()
    await session.close()
    assert (await _state(late_id))[0] == BookingStatus.OVERRIDDEN.value


@pytest.mark.asyncio
async def test_competing_create_waits_for_series_confirmation_then_conflicts(monkeypatch, world):
    draft_id = await _saved_draft(monkeypatch, world)
    series_session, competitor_session = _session(), _session()
    _as_user(monkeypatch, world.steward_id)
    draft_service = _draft_service(series_session, StubRecurringOverrideNotifier())
    _as_user(monkeypatch, world.other_user_id)
    competitor = _booking_service(competitor_session)

    await draft_service.confirm_draft(draft_id)
    start_at, end_at = _interval(world.dates[2])
    racing = asyncio.create_task(
        competitor.create_booking(
            CreateBookingCommand(title="EFC-259 race", start_at=start_at, end_at=end_at, rooms=[BookingRoomLineCommand(facility_id=world.room_id, sequence=0)])
        )
    )
    await asyncio.sleep(0.5)
    assert not racing.done(), "competing create must wait for the Series confirmation's room lock"

    await series_session.commit()
    with pytest.raises(ConflictErrorException) as exc_info:
        await racing
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    await competitor_session.rollback()
    await series_session.close()
    await competitor_session.close()
