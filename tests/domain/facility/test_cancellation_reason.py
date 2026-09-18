"""Member cancellation reason normalization."""

import pytest

from portal.domain.facility.cancellation_reason import InvalidMemberCancellationReason, normalize_member_cancellation_reason


def test_normalize_member_cancellation_reason_trims_and_keeps_plain_text():
    assert normalize_member_cancellation_reason("  Room no longer needed  ") == "Room no longer needed"


def test_normalize_member_cancellation_reason_accepts_one_and_two_hundred_fifty_characters():
    assert normalize_member_cancellation_reason("A") == "A"
    assert normalize_member_cancellation_reason("a" * 250) == "a" * 250


def test_normalize_member_cancellation_reason_rejects_empty_or_whitespace():
    with pytest.raises(InvalidMemberCancellationReason, match="1 and 250"):
        normalize_member_cancellation_reason("")
    with pytest.raises(InvalidMemberCancellationReason, match="1 and 250"):
        normalize_member_cancellation_reason("   ")


def test_normalize_member_cancellation_reason_rejects_more_than_two_hundred_fifty_characters():
    with pytest.raises(InvalidMemberCancellationReason, match="1 and 250"):
        normalize_member_cancellation_reason("a" * 251)
