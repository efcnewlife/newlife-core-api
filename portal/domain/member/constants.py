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
