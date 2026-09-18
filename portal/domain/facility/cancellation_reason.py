"""Member cancellation reason rules."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator

MEMBER_CANCELLATION_REASON_MIN_LENGTH = 1
MEMBER_CANCELLATION_REASON_MAX_LENGTH = 250


class InvalidMemberCancellationReason(ValueError):
    """Raised when a member cancellation reason is missing or too long."""


def normalize_member_cancellation_reason(value: str) -> str:
    """Trim and validate a required 1-250-character cancellation reason."""
    if not isinstance(value, str):
        raise InvalidMemberCancellationReason("Cancellation reason must be between 1 and 250 characters")
    trimmed = value.strip()
    if len(trimmed) < MEMBER_CANCELLATION_REASON_MIN_LENGTH or len(trimmed) > MEMBER_CANCELLATION_REASON_MAX_LENGTH:
        raise InvalidMemberCancellationReason("Cancellation reason must be between 1 and 250 characters")
    return trimmed


MemberCancellationReason = Annotated[str, AfterValidator(normalize_member_cancellation_reason)]
