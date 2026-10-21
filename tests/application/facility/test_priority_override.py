"""
Priority Ministry override review acknowledgement (reviewed impact token) tests.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from portal.application.facility.priority_override import issue_override_review_token, require_reviewed_override
from portal.application.facility.results import OverrideImpactResult, OverrideReleasedIntervalResult
from portal.domain.facility.constants import BookingErrorCode
from portal.exceptions.responses import ConflictErrorException

SECRET = b"test-secret"
START = datetime(2026, 11, 2, 15, 0, tzinfo=timezone.utc)
END = datetime(2026, 11, 2, 17, 0, tzinfo=timezone.utc)


def _impact(booking_id=None, *, rooms=None) -> OverrideImpactResult:
    rooms = rooms or [uuid4()]
    return OverrideImpactResult(
        booking_id=booking_id or uuid4(),
        start_at=START,
        end_at=END,
        released_intervals=[OverrideReleasedIntervalResult(facility_id=room, start_at=START, end_at=END) for room in rooms],
    )


def _context(**overrides):
    values = dict(booker_id=uuid4(), ministry_id=uuid4(), proposal=["room-a|10:00|12:00"])
    values.update(overrides)
    return values


def test_no_impacts_needs_no_token():
    require_reviewed_override(token=None, impacts=[], secret=SECRET, **_context())


@pytest.mark.parametrize("token", [None, ""])
def test_missing_token_with_impacts_is_review_required(token):
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=[_impact()], secret=SECRET, **_context())
    assert exc_info.value.status_code == 409
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_REQUIRED.value


def test_reviewed_unchanged_impacts_proceed():
    context = _context()
    impacts = [_impact(), _impact()]
    token = issue_override_review_token(impacts=impacts, secret=SECRET, **context)
    require_reviewed_override(token=token, impacts=impacts, secret=SECRET, **context)


def test_subset_of_reviewed_impacts_proceeds():
    context = _context()
    impacts = [_impact(), _impact()]
    token = issue_override_review_token(impacts=impacts, secret=SECRET, **context)
    require_reviewed_override(token=token, impacts=impacts[:1], secret=SECRET, **context)


def test_new_target_is_stale():
    context = _context()
    reviewed = [_impact()]
    token = issue_override_review_token(impacts=reviewed, secret=SECRET, **context)
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=[*reviewed, _impact()], secret=SECRET, **context)
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


def test_expanded_target_release_is_stale():
    context = _context()
    booking_id = uuid4()
    room = uuid4()
    token = issue_override_review_token(impacts=[_impact(booking_id, rooms=[room])], secret=SECRET, **context)
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=[_impact(booking_id, rooms=[room, uuid4()])], secret=SECRET, **context)
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


@pytest.mark.parametrize("field", ["booker_id", "ministry_id", "proposal"])
def test_changed_context_is_stale(field):
    context = _context()
    impacts = [_impact()]
    token = issue_override_review_token(impacts=impacts, secret=SECRET, **context)
    changed = dict(context)
    changed[field] = ["room-b|10:00|12:00"] if field == "proposal" else uuid4()
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=impacts, secret=SECRET, **changed)
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


@pytest.mark.parametrize("token", ["garbage", "abc.def", ".", "e30.AAAA"])
def test_forged_or_malformed_token_is_stale(token):
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=[_impact()], secret=SECRET, **_context())
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


def test_token_signed_with_other_secret_is_stale():
    context = _context()
    impacts = [_impact()]
    token = issue_override_review_token(impacts=impacts, secret=b"other", **context)
    with pytest.raises(ConflictErrorException) as exc_info:
        require_reviewed_override(token=token, impacts=impacts, secret=SECRET, **context)
    assert exc_info.value.error_code == BookingErrorCode.OVERRIDE_REVIEW_STALE.value


def test_token_is_opaque():
    context = _context()
    impacts = [_impact()]
    token = issue_override_review_token(impacts=impacts, secret=SECRET, **context)
    assert str(impacts[0].booking_id) not in token
    assert str(context["booker_id"]) not in token
