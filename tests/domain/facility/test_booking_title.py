"""Booking and Recurring Booking Series title normalization."""

import pytest

from portal.domain.facility.booking_title import InvalidBookingTitle, normalize_booking_title


def test_normalize_booking_title_trims_and_keeps_plain_text():
    assert normalize_booking_title("  Choir practice  ") == "Choir practice"


def test_normalize_booking_title_accepts_one_and_thirty_characters():
    assert normalize_booking_title("A") == "A"
    assert normalize_booking_title("a" * 30) == "a" * 30


def test_normalize_booking_title_rejects_empty_or_whitespace():
    with pytest.raises(InvalidBookingTitle, match="1 and 30"):
        normalize_booking_title("")
    with pytest.raises(InvalidBookingTitle, match="1 and 30"):
        normalize_booking_title("   ")


def test_normalize_booking_title_rejects_more_than_thirty_characters():
    with pytest.raises(InvalidBookingTitle, match="1 and 30"):
        normalize_booking_title("a" * 31)


def test_normalize_booking_title_rejects_markup():
    with pytest.raises(InvalidBookingTitle, match="plain text"):
        normalize_booking_title("<b>Choir</b>")
    with pytest.raises(InvalidBookingTitle, match="plain text"):
        normalize_booking_title("<i>Choir</i>")


def test_normalize_booking_title_allows_comparison_characters():
    assert normalize_booking_title("Choir > Youth") == "Choir > Youth"
    assert normalize_booking_title("A < B") == "A < B"
