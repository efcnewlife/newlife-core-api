"""
Focused member serializer redaction matrix for Timetable and conflict projections.
"""

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import uuid4

from portal.application.facility.mappers import (
    booking_draft_result_to_api,
    recurring_booking_preview_to_member_api,
    recurring_series_draft_result_to_api,
    room_availability_list_to_api,
)
from portal.application.facility.results import (
    BookingConflictResult,
    BookingDraftResult,
    OverrideImpactResult,
    OverrideReleasedIntervalResult,
    RecurringBookingConflictResult,
    RecurringBookingPreviewResult,
    RecurringSeriesDraftResult,
    RoomAvailabilityListResult,
    RoomAvailabilityResult,
)
from portal.domain.facility.constants import RecurringConflictKind, TimetableOccupancyKind
from portal.serializers.apis.v1.facility import MemberRecurringBookingConflict, MemberRoomAvailabilityEvent

FORBIDDEN_PERSONAL_KEYS = {
    "ministryId",
    "ministryName",
    "ministryStewardDisplayName",
    "ministryStewardEmail",
    "bookerDisplayName",
    "bookerEmail",
    "contactDisplayName",
    "contactEmail",
    "occupancyKind",
}


def _flatten_keys(value) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys |= _flatten_keys(child)
    elif isinstance(value, list):
        for child in value:
            keys |= _flatten_keys(child)
    return keys


def test_personal_availability_api_omits_events_and_contact_fields():
    room_id = uuid4()
    result = RoomAvailabilityListResult(
        date=date(2026, 7, 20),
        facility_timezone="America/Toronto",
        max_booking_lines=10,
        items=[RoomAvailabilityResult(id=room_id, code="gym", name="Gym", events=[])],
    )
    dumped = room_availability_list_to_api(result).model_dump(by_alias=True)
    assert dumped["items"][0]["events"] == []
    assert FORBIDDEN_PERSONAL_KEYS.isdisjoint(_flatten_keys(dumped["items"][0]))


def test_ministry_availability_event_serializer_exposes_authorized_contacts_only():
    event = MemberRoomAvailabilityEvent(
        start="10:00",
        end="11:00",
        occupancy_kind=TimetableOccupancyKind.MINISTRY.value,
        ministry_name="Youth",
        contact_display_name="Pat Steward",
        contact_email="pat.steward@efcnewlife.org",
    )
    dumped = event.model_dump(by_alias=True)
    assert dumped == {
        "start": "10:00",
        "end": "11:00",
        "occupancyKind": "ministry",
        "isOverridable": False,
        "ministryName": "Youth",
        "contactDisplayName": "Pat Steward",
        "contactEmail": "pat.steward@efcnewlife.org",
    }


def test_personal_conflict_serializer_redacts_ministry_and_booker_fields():
    conflict = MemberRecurringBookingConflict(
        occurrence_date=date(2026, 1, 13),
        kind=RecurringConflictKind.OCCUPANCY.value,
        facility_ids=[uuid4()],
        ministry_id=None,
        ministry_steward_display_name=None,
        ministry_steward_email=None,
        booker_display_name=None,
        booker_email=None,
    )
    dumped = conflict.model_dump(by_alias=True)
    assert dumped["kind"] == "occupancy"
    assert dumped["ministryId"] is None
    assert dumped["ministryStewardDisplayName"] is None
    assert dumped["ministryStewardEmail"] is None
    assert dumped["bookerDisplayName"] is None
    assert dumped["bookerEmail"] is None


def test_personal_preview_mapper_does_not_emit_ministry_kind_or_contacts():
    room_id = uuid4()
    result = RecurringBookingPreviewResult(
        conflicts=[RecurringBookingConflictResult(occurrence_date=date(2026, 1, 13), kind=RecurringConflictKind.OCCUPANCY.value, facility_ids=[room_id])],
        quoted_amount=Decimal("600"),
        currency="CAD",
    )
    dumped = recurring_booking_preview_to_member_api(result).model_dump(by_alias=True)
    conflict = dumped["conflicts"][0]
    assert conflict["kind"] == "occupancy"
    assert conflict["ministryId"] is None
    assert conflict["ministryStewardDisplayName"] is None
    assert conflict["ministryStewardEmail"] is None
    assert conflict["bookerDisplayName"] is None
    assert conflict["bookerEmail"] is None


def test_series_draft_mapper_preserves_redacted_personal_conflicts():
    draft = RecurringSeriesDraftResult(
        id=uuid4(),
        first_occurrence_date=date(2026, 1, 6),
        last_occurrence_date=date(2026, 2, 10),
        local_start_time=time(10, 0),
        local_end_time=time(12, 0),
        conflicts=[RecurringBookingConflictResult(occurrence_date=date(2026, 1, 13), kind=RecurringConflictKind.OCCUPANCY.value, facility_ids=[uuid4()])],
        is_confirmable=False,
        quoted_amount=Decimal("400"),
        subtotal_amount=Decimal("400"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
        surcharge_amount=Decimal("0"),
        currency="CAD",
        occurrence_count=4,
        pending_payment_hold_days=3,
        payment_hold_expires_at=datetime(2026, 1, 9, 17, 0, tzinfo=timezone.utc),
    )
    dumped = recurring_series_draft_result_to_api(draft).model_dump(by_alias=True)
    assert dumped["conflicts"][0]["kind"] == "occupancy"
    assert dumped["conflicts"][0]["ministryId"] is None
    assert dumped["ministryId"] is None


def _booking_draft(**overrides) -> BookingDraftResult:
    values = dict(
        id=uuid4(),
        title="Retreat",
        date=date(2026, 5, 1),
        subtotal_amount=Decimal("100"),
        discount_percent=Decimal("0"),
        discount_amount=Decimal("0"),
        surcharge_amount=Decimal("0"),
        quoted_amount=Decimal("100"),
        currency="CAD",
    )
    values.update(overrides)
    return BookingDraftResult(**values)


def test_personal_booking_draft_conflicts_carry_no_ministry_or_contact_values():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    draft = _booking_draft(
        is_confirmable=False, conflicts=[BookingConflictResult(facility_id=uuid4(), start_at=start, end_at=end, kind=RecurringConflictKind.OCCUPANCY.value)]
    )
    dumped = booking_draft_result_to_api(draft).model_dump(by_alias=True)
    conflict = dumped["conflicts"][0]
    assert conflict["kind"] == "occupancy"
    assert all(conflict[key] is None for key in ("ministryName", "contactDisplayName", "contactEmail"))
    assert dumped["overrideImpacts"] == []
    assert dumped["overrideReviewToken"] is None
    assert dumped["isConfirmable"] is False


def test_priority_booking_draft_exposes_whole_booking_impact_without_occupant_identity():
    start = datetime(2026, 5, 1, 14, 0, tzinfo=timezone.utc)
    end = datetime(2026, 5, 1, 16, 0, tzinfo=timezone.utc)
    room_a, room_b, booking_id = uuid4(), uuid4(), uuid4()
    draft = _booking_draft(
        override_impacts=[
            OverrideImpactResult(
                booking_id=booking_id,
                is_series_occurrence=True,
                start_at=start,
                end_at=end,
                released_intervals=[
                    OverrideReleasedIntervalResult(facility_id=room_a, start_at=start, end_at=end),
                    OverrideReleasedIntervalResult(facility_id=room_b, start_at=start, end_at=end),
                ],
            )
        ],
        override_review_token="opaque",
    )
    dumped = booking_draft_result_to_api(draft).model_dump(by_alias=True)
    impact = dumped["overrideImpacts"][0]
    assert impact["bookingId"] == booking_id
    assert impact["isSeriesOccurrence"] is True
    assert [item["facilityId"] for item in impact["releasedIntervals"]] == [room_a, room_b]
    assert {"bookerDisplayName", "bookerEmail", "title", "userId"}.isdisjoint(_flatten_keys(impact))
    assert dumped["overrideReviewToken"] == "opaque"
