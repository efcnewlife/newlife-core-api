"""
Reviewed Recurring Priority Ministry override: preview/Draft review and final Series confirmation (EFC-259).
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.commands import BookingRoomLineCommand, CreateRecurringBookingSeriesCommand
from portal.application.facility.recurring_booking_service import RecurringBookingService
from portal.application.facility.recurring_series_draft_service import RecurringSeriesDraftService
from portal.application.facility.results import (
    OverrideReleasedIntervalResult,
    RecurringOccupyingBookingResult,
    RecurringSeriesDraftDetailResult,
    RecurringSeriesDraftStoredRoomResult,
)
from portal.application.org.results import MinistryMemberResult
from portal.domain.facility.constants import BookingErrorCode, FacilityErrorCode, OverrideOutcome
from portal.domain.facility.recurring import localize_wall_time
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.exceptions.responses import ConflictErrorException
from tests.fixtures.facility.factories import make_ministry_detail, make_preview_quote_result, new_uuid
from tests.fixtures.facility.stubs import (
    StubBookingRepository,
    StubMinistryRepository,
    StubOverrideLogRepository,
    StubPricingService,
    StubRecurringBookingRepository,
    StubRecurringOverrideNotifier,
    StubRecurringSeriesDraftRepository,
    StubRoomBlackoutRepository,
    StubRoomSlotTemplateRepository,
    StubTransactionHooks,
    StubUserReadService,
)
from tests.fixtures.system.stubs import StubSettingService

SECRET = b"recurring-review-secret"
TORONTO = ZoneInfo("America/Toronto")
NOW = datetime(2025, 12, 8, 17, 0, tzinfo=timezone.utc)
FIRST = date(2026, 1, 6)
LAST = date(2026, 2, 10)
SECOND = date(2026, 1, 13)
THIRD = date(2026, 1, 20)


def _start(occurrence_date: date) -> datetime:
    return localize_wall_time(occurrence_date, time(10, 0), TORONTO).astimezone(timezone.utc)


def _rental(room_id, occurrence_date, *, booking_id=None, user_id=None, series_id=None, ministry_id=None) -> RecurringOccupyingBookingResult:
    start = _start(occurrence_date)
    return RecurringOccupyingBookingResult(
        booking_id=booking_id or uuid4(),
        user_id=user_id or uuid4(),
        ministry_id=ministry_id,
        facility_ids=[room_id],
        start_at=start,
        end_at=start + timedelta(hours=2),
        booker_display_name="Rita Renter",
        booker_email="rita@example.com",
        series_id=series_id,
    )


class _Harness:
    def __init__(self, monkeypatch, *, occupants=(), is_priority=True, personal=False, members=None):
        self.booker_id = uuid4()
        self.room_id = new_uuid()
        self.ministry_id = None if personal else new_uuid()
        ctx = type("UserCtx", (), {})()
        ctx.user_id = self.booker_id
        ctx.email = "steward@efcnewlife.org"
        ctx.username = "steward"
        monkeypatch.setattr("portal.application.facility.recurring_booking_service.get_user_context", lambda: ctx)
        monkeypatch.setattr("portal.application.facility.recurring_series_draft_service.get_user_context", lambda: ctx)
        ministries = {}
        if self.ministry_id is not None:
            ministry = make_ministry_detail(self.ministry_id)
            ministry.status = MinistryStatus.ACTIVE.value
            ministry.has_priority_booking = is_priority
            ministry.name = "Choir"
            ministries[self.ministry_id] = ministry
        self.ministries = StubMinistryRepository(ministry_by_id=ministries, booking_member_user_ids={self.booker_id}, members_by_ministry=members or {})
        self.bookings = StubBookingRepository(occupying_bookings=list(occupants))
        self.series = StubRecurringBookingRepository()
        self.drafts = StubRecurringSeriesDraftRepository()
        self.logs = StubOverrideLogRepository()
        self.hooks = StubTransactionHooks()
        self.notifier = StubRecurringOverrideNotifier()
        self.recurring = RecurringBookingService(
            series_repository=self.series,
            booking_repository=self.bookings,
            pricing_service=StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
            ministry_repository=self.ministries,
            room_blackout_repository=StubRoomBlackoutRepository(),
            setting_service=StubSettingService(max_booking_lines=10),
            user_read_service=StubUserReadService(email="steward@efcnewlife.org"),
            override_log_repository=self.logs,
            room_slot_template_repository=StubRoomSlotTemplateRepository(),
            transaction_hooks=self.hooks,
            override_notifier=self.notifier,
            now_utc=lambda: NOW,
            review_secret=SECRET,
        )
        self.service = RecurringSeriesDraftService(self.drafts, self.recurring)

    def command(self, **overrides) -> CreateRecurringBookingSeriesCommand:
        return CreateRecurringBookingSeriesCommand(
            title=overrides.pop("title", "Choir"),
            ministry_id=overrides.pop("ministry_id", self.ministry_id),
            first_occurrence_date=FIRST,
            last_occurrence_date=LAST,
            local_start_time=time(10, 0),
            local_end_time=time(12, 0),
            rooms=overrides.pop("rooms", [BookingRoomLineCommand(facility_id=self.room_id, sequence=0)]),
            **overrides,
        )

    def store_draft(self, *, excluded_dates=(), title="Choir") -> uuid4:
        draft_id = uuid4()
        self.drafts.draft_by_id[draft_id] = RecurringSeriesDraftDetailResult(
            id=draft_id,
            user_id=self.booker_id,
            title=title,
            ministry_id=self.ministry_id,
            first_occurrence_date=FIRST,
            last_occurrence_date=LAST,
            local_start_time=time(10, 0),
            local_end_time=time(12, 0),
            excluded_dates=list(excluded_dates),
            rooms=[RecurringSeriesDraftStoredRoomResult(facility_id=self.room_id, sequence=0)],
        )
        return draft_id

    def assert_no_writes(self):
        assert self.series.insert_series_calls == []
        assert self.bookings.insert_calls == []
        assert self.bookings.override_calls == []
        assert self.logs.insert_calls == []
        assert self.hooks.callbacks == []


# --- review (preview and Draft read) ---


@pytest.mark.asyncio
async def test_draft_review_returns_whole_booking_impacts_and_token_without_side_effects(monkeypatch):
    target_id = uuid4()
    harness = _Harness(monkeypatch)
    rental = _rental(harness.room_id, SECOND, booking_id=target_id)
    harness.bookings.occupying_bookings = [rental]
    other_room = new_uuid()
    harness.bookings.live_slot_intervals[target_id] = [
        OverrideReleasedIntervalResult(facility_id=harness.room_id, start_at=rental.start_at, end_at=rental.end_at),
        OverrideReleasedIntervalResult(facility_id=other_room, start_at=rental.start_at, end_at=rental.end_at),
    ]
    draft_id = harness.store_draft()

    result = await harness.service.get_draft(draft_id)

    assert result.is_confirmable is True
    assert [impact.booking_id for impact in result.override_impacts] == [target_id]
    assert {item.facility_id for item in result.override_impacts[0].released_intervals} == {harness.room_id, other_room}
    assert result.override_review_token
    harness.assert_no_writes()
    assert harness.notifier.calls == []


@pytest.mark.asyncio
async def test_draft_review_without_impact_has_no_token(monkeypatch):
    harness = _Harness(monkeypatch)
    result = await harness.service.get_draft(harness.store_draft())
    assert result.is_confirmable is True
    assert result.override_impacts == []
    assert result.override_review_token is None


@pytest.mark.asyncio
async def test_draft_review_excluded_date_is_not_an_impact(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    result = await harness.service.get_draft(harness.store_draft(excluded_dates=[SECOND]))
    assert result.is_confirmable is True
    assert result.override_impacts == []
    assert result.override_review_token is None


@pytest.mark.asyncio
async def test_unconfirmable_draft_review_lists_impacts_without_token(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    result = await harness.service.get_draft(harness.store_draft(title=None))
    assert result.is_confirmable is False
    assert len(result.override_impacts) == 1
    assert result.override_review_token is None


@pytest.mark.asyncio
async def test_preview_issues_token_for_member_direct_create(monkeypatch):
    harness = _Harness(monkeypatch)
    target_id = uuid4()
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, booking_id=target_id)]

    preview = await harness.recurring.preview_conflicts(harness.command())
    assert [impact.booking_id for impact in preview.override_impacts] == [target_id]
    assert preview.override_review_token
    harness.assert_no_writes()

    result = await harness.recurring.create_series(harness.command(override_review_token=preview.override_review_token))
    assert result.occurrence_count == 6
    assert [call["booking_id"] for call in harness.bookings.override_calls] == [target_id]


@pytest.mark.asyncio
async def test_personal_preview_has_no_override_impacts(monkeypatch):
    harness = _Harness(monkeypatch, personal=True)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    preview = await harness.recurring.preview_conflicts(harness.command())
    assert preview.override_impacts == []
    assert preview.override_review_token is None


# --- final confirmation ---


@pytest.mark.asyncio
async def test_confirm_reviewed_draft_commits_series_overrides_audit_and_consumes_draft(monkeypatch):
    target_id = uuid4()
    displaced_booker = uuid4()
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, booking_id=target_id, user_id=displaced_booker)]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token

    result = await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert result.occurrence_count == 6
    assert harness.bookings.override_calls == [dict(booking_id=target_id, overridden_by_id=harness.booker_id, reason="Priority Ministry override")]
    log = harness.logs.insert_calls[0][0]
    assert log["overridden_booking_id"] == target_id
    assert log["facility_booking_id"] in {item.id for item in result.occurrences}
    assert log["outcome"] == OverrideOutcome.OVERRIDE_APPLIED.value
    assert harness.drafts.delete_draft_calls == [draft_id]
    assert harness.notifier.calls == []

    await harness.hooks.commit()
    assert len(harness.notifier.calls) == 1
    assert harness.notifier.calls[0].series_id == result.id
    assert harness.notifier.calls[0].affected_booker_ids == [displaced_booker]


@pytest.mark.asyncio
async def test_rolled_back_confirmation_sends_no_mail(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token
    await harness.service.confirm_draft(draft_id, override_review_token=token)

    harness.hooks.rollback()
    await harness.hooks.commit()
    assert harness.notifier.calls == []


@pytest.mark.asyncio
async def test_confirm_without_review_is_rejected_and_writes_nothing(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    draft_id = harness.store_draft()

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id)

    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_REQUIRED.value
    harness.assert_no_writes()
    assert draft_id in harness.drafts.draft_by_id


@pytest.mark.asyncio
async def test_no_override_draft_confirms_without_token(monkeypatch):
    harness = _Harness(monkeypatch)
    draft_id = harness.store_draft()
    result = await harness.service.confirm_draft(draft_id)
    assert result.occurrence_count == 6
    assert harness.bookings.override_calls == []


@pytest.mark.asyncio
async def test_new_personal_target_after_review_is_stale(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token
    harness.bookings.occupying_bookings.append(_rental(harness.room_id, THIRD))

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_changed_target_intervals_after_review_is_stale(monkeypatch):
    target_id = uuid4()
    harness = _Harness(monkeypatch)
    rental = _rental(harness.room_id, SECOND, booking_id=target_id)
    harness.bookings.occupying_bookings = [rental]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token
    harness.bookings.live_slot_intervals[target_id] = [
        OverrideReleasedIntervalResult(facility_id=harness.room_id, start_at=rental.start_at, end_at=rental.end_at),
        OverrideReleasedIntervalResult(facility_id=new_uuid(), start_at=rental.start_at, end_at=rental.end_at),
    ]

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_unchanged_subset_of_reviewed_targets_proceeds(monkeypatch):
    kept_id = uuid4()
    harness = _Harness(monkeypatch)
    kept = _rental(harness.room_id, SECOND, booking_id=kept_id)
    gone = _rental(harness.room_id, THIRD)
    harness.bookings.occupying_bookings = [kept, gone]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token
    harness.bookings.occupying_bookings = [kept]

    await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert [call["booking_id"] for call in harness.bookings.override_calls] == [kept_id]


@pytest.mark.asyncio
async def test_token_is_bound_to_explicit_excluded_dates(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND), _rental(harness.room_id, THIRD)]
    token = (await harness.recurring.preview_conflicts(harness.command())).override_review_token

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.recurring.create_series(harness.command(excluded_dates=[THIRD], override_review_token=token))

    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_excluded_date_creates_no_occurrence_and_displaces_nothing(monkeypatch):
    kept_id = uuid4()
    excluded_target = uuid4()
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, booking_id=kept_id), _rental(harness.room_id, THIRD, booking_id=excluded_target)]
    draft_id = harness.store_draft(excluded_dates=[THIRD])
    token = (await harness.service.get_draft(draft_id)).override_review_token

    result = await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert result.occurrence_count == 5
    assert all(item.start_at != _start(THIRD) for item in result.occurrences)
    assert [call["booking_id"] for call in harness.bookings.override_calls] == [kept_id]


@pytest.mark.asyncio
async def test_lost_priority_after_review_blocks_instead_of_displacing(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    draft_id = harness.store_draft()
    token = (await harness.service.get_draft(draft_id)).override_review_token
    harness.ministries.ministry_by_id[harness.ministry_id].has_priority_booking = False

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id, override_review_token=token)

    assert exc_info.value.context["invalidity_code"] == BookingErrorCode.SCHEDULING_CONFLICT.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_competing_occupancy_at_final_confirmation_returns_safe_scheduling_conflict(monkeypatch):
    harness = _Harness(monkeypatch)
    draft_id = harness.store_draft()
    command = harness.command()
    await harness.service.get_draft(draft_id)
    started = _rental(harness.room_id, SECOND).model_copy(update={"start_at": NOW - timedelta(hours=1)})
    harness.bookings.occupying_bookings = [started]

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.recurring.create_series(command)

    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert "occupying_bookings" not in str(exc_info.value.context)
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_only_the_affected_occurrence_of_a_target_series_is_displaced(monkeypatch):
    occurrence_id = uuid4()
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, booking_id=occurrence_id, series_id=uuid4())]
    draft_id = harness.store_draft()
    review = await harness.service.get_draft(draft_id)
    assert review.override_impacts[0].is_series_occurrence is True

    await harness.service.confirm_draft(draft_id, override_review_token=review.override_review_token)

    assert [call["booking_id"] for call in harness.bookings.override_calls] == [occurrence_id]
    assert harness.series.update_series_calls == []


@pytest.mark.asyncio
async def test_protected_ministry_target_keeps_authorized_contact(monkeypatch):
    other_ministry = new_uuid()
    harness = _Harness(
        monkeypatch,
        members={
            other_ministry: [
                MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat Steward", email="pat@efcnewlife.org")
            ]
        },
    )
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, ministry_id=other_ministry)]
    draft_id = harness.store_draft()

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id)

    conflict = exc_info.value.context["conflicts"][0]
    assert conflict["ministry_steward_email"] == "pat@efcnewlife.org"
    assert "occupying_bookings" not in conflict
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_personal_draft_conflict_context_never_exposes_occupant(monkeypatch):
    harness = _Harness(monkeypatch, personal=True)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND, ministry_id=new_uuid())]
    draft_id = harness.store_draft()

    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.confirm_draft(draft_id)

    context = str(exc_info.value.context)
    assert "rita@example.com" not in context
    assert "Rita Renter" not in context
    assert "occupying_bookings" not in context


@pytest.mark.asyncio
async def test_admin_create_keeps_unreviewed_override_with_mail_after_commit(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]

    await harness.recurring.create_series(harness.command(require_override_review=False))

    assert len(harness.bookings.override_calls) == 1
    assert harness.notifier.calls == []
    await harness.hooks.commit()
    assert len(harness.notifier.calls) == 1


@pytest.mark.asyncio
async def test_mail_failure_after_commit_does_not_undo_series(monkeypatch):
    harness = _Harness(monkeypatch)
    harness.notifier.raise_error = RuntimeError("graph down")
    harness.bookings.occupying_bookings = [_rental(harness.room_id, SECOND)]
    token = (await harness.recurring.preview_conflicts(harness.command())).override_review_token

    result = await harness.recurring.create_series(harness.command(override_review_token=token))

    assert result.occurrence_count == 6
    assert len(harness.hooks.callbacks) == 1
