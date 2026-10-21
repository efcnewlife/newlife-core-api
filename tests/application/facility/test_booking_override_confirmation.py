"""
One-time Priority Ministry override final confirmation (EFC-258).
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from portal.application.facility.booking_line_validation import ResolvedBookingLine
from portal.application.facility.booking_service import BookingService
from portal.application.facility.commands import BookingRoomLineCommand
from portal.application.facility.one_time_override import one_time_proposal
from portal.application.facility.priority_override import issue_override_review_token
from portal.application.facility.results import BookingDraftDetailResult, OverrideImpactResult, OverrideReleasedIntervalResult, RecurringOccupyingBookingResult
from portal.application.org.results import MinistryMemberResult
from portal.domain.facility.constants import BookingErrorCode, OverrideOutcome
from portal.domain.org.constants import MinistryMemberRole
from portal.exceptions.responses import BadRequestException, ConflictErrorException
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


class _Harness:
    def __init__(self, monkeypatch, *, occupants, is_priority=True, ministry_id=None, booker_id=None, steward_ids=None, draft=None, members=None):
        self.booker_id = booker_id or uuid4()
        self.ministry_id = ministry_id
        ctx = type("UserCtx", (), {})()
        ctx.user_id = self.booker_id
        monkeypatch.setattr("portal.application.facility.booking_service.get_user_context", lambda: ctx)
        ministries = {}
        if ministry_id is not None:
            ministries[ministry_id] = make_ministry_detail(ministry_id).model_copy(update={"has_priority_booking": is_priority})
        self.bookings = StubBookingRepository(occupying_bookings=occupants)
        self.ministries = StubMinistryRepository(
            ministry_by_id=ministries, booking_member_user_ids=steward_ids if steward_ids is not None else {self.booker_id}, members_by_ministry=members or {}
        )
        self.drafts = StubBookingDraftRepository({draft.id: draft} if draft else None)
        self.logs = StubOverrideLogRepository()
        self.hooks = StubTransactionHooks()
        self.notifier = StubRecurringOverrideNotifier()
        self.service = BookingService(
            self.bookings,
            StubPricingService(make_preview_quote_result(quoted_amount=Decimal("100"))),
            self.ministries,
            StubRoomBlackoutRepository(),
            StubSettingService(),
            self.drafts,
            StubFileService(),
            StubRoomSlotTemplateRepository(),
            self.logs,
            self.hooks,
            self.notifier,
            now_utc=lambda: NOW,
            review_secret=SECRET,
        )

    def assert_no_writes(self):
        assert self.bookings.insert_calls == []
        assert self.bookings.override_calls == []
        assert self.logs.insert_calls == []
        assert self.drafts.delete_draft_calls == []
        assert self.hooks.callbacks == []


def _rental(facility_ids, *, start=START, end=END, user_id=None, series_id=None, ministry_id=None, **extra):
    return RecurringOccupyingBookingResult(
        booking_id=uuid4(),
        user_id=user_id or uuid4(),
        ministry_id=ministry_id,
        facility_ids=list(facility_ids),
        start_at=start,
        end_at=end,
        series_id=series_id,
        booker_display_name=extra.get("booker_display_name", "Rita Renter"),
        booker_email=extra.get("booker_email", "rita@example.com"),
        ministry_name=extra.get("ministry_name"),
    )


def _command(harness, rooms, *, token=None, member=True, draft_id=None):
    command = make_create_booking_command(facility_id=rooms[0], start_at=START, end_at=END, ministry_id=harness.ministry_id, booking_draft_id=draft_id)
    command.rooms = [BookingRoomLineCommand(facility_id=room, sequence=index) for index, room in enumerate(rooms)]
    command.allow_priority_override = member
    command.override_review_token = token
    return command


def _token(harness, rooms, impacts):
    lines = [ResolvedBookingLine(facility_id=room, start_at=START, end_at=END, sequence=index) for index, room in enumerate(rooms)]
    return issue_override_review_token(
        booker_id=harness.booker_id, ministry_id=harness.ministry_id, proposal=one_time_proposal(lines), impacts=impacts, secret=SECRET
    )


def _impact(occupant, released=None) -> OverrideImpactResult:
    intervals = released or [
        OverrideReleasedIntervalResult(facility_id=room, start_at=occupant.start_at, end_at=occupant.end_at) for room in occupant.facility_ids
    ]
    return OverrideImpactResult(
        booking_id=occupant.booking_id,
        is_series_occurrence=occupant.series_id is not None,
        start_at=occupant.start_at,
        end_at=occupant.end_at,
        released_intervals=intervals,
    )


@pytest.mark.asyncio
async def test_override_without_review_token_is_review_required_and_writes_nothing(monkeypatch):
    room = uuid4()
    harness = _Harness(monkeypatch, occupants=[_rental([room])], ministry_id=uuid4())
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room]))
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_REQUIRED.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_reviewed_override_replaces_whole_multi_room_booking_atomically(monkeypatch):
    room_a, room_b, other_room = uuid4(), uuid4(), uuid4()
    target = _rental([room_a, room_b])
    draft_id = uuid4()
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    harness.drafts.draft_by_id[draft_id] = BookingDraftDetailResult(
        id=draft_id, user_id=harness.booker_id, title="Retreat", date=START.date(), ministry_id=harness.ministry_id, lines=[]
    )
    released = [
        OverrideReleasedIntervalResult(facility_id=room_a, start_at=START, end_at=END),
        OverrideReleasedIntervalResult(facility_id=room_b, start_at=START, end_at=END),
        OverrideReleasedIntervalResult(facility_id=other_room, start_at=START + timedelta(hours=3), end_at=END + timedelta(hours=3)),
    ]
    harness.bookings.live_slot_intervals[target.booking_id] = released
    token = _token(harness, [room_a, room_b], [_impact(target, released)])

    result = await harness.service.create_booking(_command(harness, [room_a, room_b], token=token, draft_id=draft_id))

    assert harness.bookings.lock_rooms_calls == [[room_a, room_b]]
    assert [call["booking_id"] for call in harness.bookings.override_calls] == [target.booking_id]
    log_rows = harness.logs.insert_calls[0]
    assert {(row["facility_id"], row["facility_booking_id"], row["overridden_booking_id"]) for row in log_rows} == {
        (room_a, result.id, target.booking_id),
        (room_b, result.id, target.booking_id),
    }
    assert all(row["outcome"] == OverrideOutcome.OVERRIDE_APPLIED.value for row in log_rows)
    assert harness.drafts.delete_draft_calls == [draft_id]
    assert harness.notifier.calls == []

    await harness.hooks.commit()

    assert len(harness.notifier.calls) == 1
    notification = harness.notifier.calls[0]
    assert notification.series_id is None
    assert notification.ministry_id == harness.ministry_id
    assert [(item.booking_id, item.booker_id) for item in notification.items] == [(target.booking_id, target.user_id)]
    assert notification.items[0].facility_ids == [room_a, room_b, other_room]
    assert notification.items[0].church_activity_booking_id == result.id


@pytest.mark.asyncio
async def test_rolled_back_confirmation_sends_no_notification(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    await harness.service.create_booking(_command(harness, [room], token=_token(harness, [room], [_impact(target)])))
    harness.hooks.rollback()
    await harness.hooks.commit()
    assert harness.notifier.calls == []


@pytest.mark.asyncio
async def test_each_displaced_booking_is_notified_once(monkeypatch):
    room_a, room_b = uuid4(), uuid4()
    shared_booker = uuid4()
    first = _rental([room_a], user_id=shared_booker)
    second = _rental([room_b], user_id=shared_booker)
    third = _rental([room_b], start=START + timedelta(hours=1))
    harness = _Harness(monkeypatch, occupants=[first, second, third], ministry_id=uuid4())
    token = _token(harness, [room_a, room_b], [_impact(first), _impact(second), _impact(third)])

    await harness.service.create_booking(_command(harness, [room_a, room_b], token=token))
    await harness.hooks.commit()

    assert len(harness.notifier.calls) == 1
    items = harness.notifier.calls[0].items
    assert sorted((item.booking_id, item.booker_id) for item in items) == sorted(
        [(first.booking_id, shared_booker), (second.booking_id, shared_booker), (third.booking_id, third.user_id)]
    )
    assert harness.notifier.calls[0].affected_booker_ids == [shared_booker, third.user_id]


@pytest.mark.asyncio
async def test_subset_of_reviewed_impact_proceeds(monkeypatch):
    room = uuid4()
    remaining = _rental([room])
    gone = _rental([uuid4()])
    harness = _Harness(monkeypatch, occupants=[remaining], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(remaining), _impact(gone)])
    await harness.service.create_booking(_command(harness, [room], token=token))
    assert [call["booking_id"] for call in harness.bookings.override_calls] == [remaining.booking_id]


@pytest.mark.asyncio
async def test_new_personal_target_after_review_is_stale(monkeypatch):
    room = uuid4()
    reviewed = _rental([room])
    newcomer = _rental([room], start=START + timedelta(minutes=30))
    harness = _Harness(monkeypatch, occupants=[reviewed, newcomer], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(reviewed)])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token))
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_expanded_target_after_review_is_stale(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(target)])
    harness.bookings.live_slot_intervals[target.booking_id] = [
        OverrideReleasedIntervalResult(facility_id=room, start_at=START, end_at=END),
        OverrideReleasedIntervalResult(facility_id=uuid4(), start_at=START, end_at=END),
    ]
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token))
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_token_for_another_proposal_is_stale(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    token = _token(harness, [uuid4()], [_impact(target)])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token))
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


@pytest.mark.asyncio
async def test_new_ministry_occupancy_blocks_with_authorized_contact(monkeypatch):
    room = uuid4()
    reviewed = _rental([room])
    other_ministry = uuid4()
    ministry_occupant = _rental([room], ministry_id=other_ministry, ministry_name="Choir", booker_display_name="Hidden Booker", booker_email="hidden@x.org")
    members = {
        other_ministry: [
            MinistryMemberResult(user_id=uuid4(), member_role=MinistryMemberRole.PRIMARY.value, display_name="Pat Steward", email="pat@efcnewlife.org")
        ]
    }
    harness = _Harness(monkeypatch, occupants=[reviewed, ministry_occupant], ministry_id=uuid4(), members=members)
    token = _token(harness, [room], [_impact(reviewed)])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert exc_info.value.context["conflicts"] == [
        {
            "facility_id": str(room),
            "start_at": "2026-05-01T14:00:00Z",
            "end_at": "2026-05-01T16:00:00Z",
            "kind": "ministry",
            "ministry_name": "Choir",
            "contact_display_name": "Pat Steward",
            "contact_email": "pat@efcnewlife.org",
        }
    ]
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_started_rental_is_protected_from_override(monkeypatch):
    room = uuid4()
    started = _rental([room], start=NOW - timedelta(minutes=1), end=END)
    harness = _Harness(monkeypatch, occupants=[started], ministry_id=uuid4())
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token="anything"))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    assert "contact_email" not in exc_info.value.context["conflicts"][0]
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_rental_starting_exactly_now_is_protected(monkeypatch):
    room = uuid4()
    harness = _Harness(monkeypatch, occupants=[_rental([room], start=NOW)], ministry_id=uuid4())
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room]))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value


@pytest.mark.asyncio
async def test_non_priority_ministry_cannot_override_but_sees_rental_booker_contact(monkeypatch):
    room = uuid4()
    harness = _Harness(monkeypatch, occupants=[_rental([room])], ministry_id=uuid4(), is_priority=False)
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room]))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    conflict = exc_info.value.context["conflicts"][0]
    assert (conflict["kind"], conflict["contact_display_name"], conflict["contact_email"]) == ("occupancy", "Rita Renter", "rita@example.com")
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_lost_priority_since_review_blocks_override(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4(), is_priority=False)
    token = _token(harness, [room], [_impact(target)])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_personal_conflict_redacts_ministry_occupant(monkeypatch):
    room = uuid4()
    ministry_occupant = _rental([room], ministry_id=uuid4(), ministry_name="Choir")
    harness = _Harness(monkeypatch, occupants=[ministry_occupant, _rental([room])])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room]))
    assert exc_info.value.context["conflicts"] == [
        {"facility_id": str(room), "start_at": "2026-05-01T14:00:00Z", "end_at": "2026-05-01T16:00:00Z", "kind": "occupancy"}
    ]


@pytest.mark.asyncio
async def test_admin_create_never_overrides(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(target)])
    with pytest.raises(ConflictErrorException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=token, member=False))
    assert exc_info.value.error_code == BookingErrorCode.SCHEDULING_CONFLICT.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_series_occurrence_target_displaces_only_that_occurrence(monkeypatch):
    room = uuid4()
    occurrence = _rental([room], series_id=uuid4())
    harness = _Harness(monkeypatch, occupants=[occurrence], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(occurrence)])
    await harness.service.create_booking(_command(harness, [room], token=token))
    assert [call["booking_id"] for call in harness.bookings.override_calls] == [occurrence.booking_id]
    assert harness.bookings.cancel_calls == []


@pytest.mark.asyncio
async def test_blackout_still_wins_over_reviewed_override(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    harness.service._blackout_repository = StubRoomBlackoutRepository(has_overlap=True)
    with pytest.raises(BadRequestException) as exc_info:
        await harness.service.create_booking(_command(harness, [room], token=_token(harness, [room], [_impact(target)])))
    assert exc_info.value.error_code == BookingErrorCode.ROOM_BLACKOUT.value
    harness.assert_no_writes()


@pytest.mark.asyncio
async def test_free_rooms_confirm_without_token(monkeypatch):
    room = uuid4()
    harness = _Harness(monkeypatch, occupants=[], ministry_id=uuid4())
    await harness.service.create_booking(_command(harness, [room]))
    assert len(harness.bookings.insert_calls) == 1
    assert harness.bookings.override_calls == []
    assert harness.hooks.callbacks == []


@pytest.mark.asyncio
async def test_review_token_accepts_same_instant_sent_with_local_offset(monkeypatch):
    room = uuid4()
    target = _rental([room])
    harness = _Harness(monkeypatch, occupants=[target], ministry_id=uuid4())
    token = _token(harness, [room], [_impact(target)])
    toronto = ZoneInfo("America/Toronto")
    command = _command(harness, [room], token=token)
    command.start_at = START.astimezone(toronto)
    command.end_at = END.astimezone(toronto)

    await harness.service.create_booking(command)

    assert [call["booking_id"] for call in harness.bookings.override_calls] == [target.booking_id]
