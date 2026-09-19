"""Booking, Booking Draft, and Recurring Booking Series title rules."""

from __future__ import annotations

import re
from typing import Annotated

from pydantic import AfterValidator

BOOKING_TITLE_MIN_LENGTH = 1
BOOKING_TITLE_MAX_LENGTH = 30

_HTML_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")


class InvalidBookingTitle(ValueError):
    """Raised when a Booking or Recurring Booking Series title is not valid plain text."""


def normalize_booking_title(value: str) -> str:
    """Trim and validate a required 1-30-character plain-text title."""
    if not isinstance(value, str):
        raise InvalidBookingTitle("Title must be between 1 and 30 characters")
    trimmed = value.strip()
    if len(trimmed) < BOOKING_TITLE_MIN_LENGTH or len(trimmed) > BOOKING_TITLE_MAX_LENGTH:
        raise InvalidBookingTitle("Title must be between 1 and 30 characters")
    if _HTML_TAG_RE.search(trimmed):
        raise InvalidBookingTitle("Title must be plain text")
    return trimmed


def _as_optional_booking_title(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_booking_title(value)


BookingTitle = Annotated[str, AfterValidator(normalize_booking_title)]
OptionalBookingTitle = Annotated[str | None, AfterValidator(_as_optional_booking_title)]
