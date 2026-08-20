"""
Member domain constants.
"""

from enum import Enum


class AccountKind(str, Enum):
    """Auth user account kind."""

    MEMBER = "member"
    GUEST = "guest"
    EXTERNAL = "external"
    SERVICE = "service"


class MemberErrorCode(str, Enum):
    """Machine-readable member admin error codes for clients."""

    PERSON_NOT_FOUND = "MEMBER_PERSON_NOT_FOUND"
    PERSON_USER_ALREADY_LINKED = "MEMBER_PERSON_USER_ALREADY_LINKED"
