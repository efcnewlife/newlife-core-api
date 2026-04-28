"""
Enums for the application - Template: Core enums only
"""
from enum import Enum, IntEnum


class APIScope(Enum):
    """API scopes"""
    ADMIN = "admin"
    API = "api"
    PUBLIC = "public"


class AccessTokenAudType(Enum):
    """Access token audience type"""
    ADMIN = "admin"
    USER = "user"


class ThirdPartyProvider(str, Enum):
    """Third-party OAuth / OIDC provider keys (auth.auth_third_party_provider.name)."""
    MICROSOFT = "microsoft"


class Gender(IntEnum):
    """Gender"""
    UNKNOWN = 0
    MALE = 1
    FEMALE = 2


class ResourceType(IntEnum):
    """Resource type"""
    SYSTEM = 0
    GENERAL = 1


class OperationType(Enum):
    """Operation Type"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"
    RECYCLE = "recycle"
    LOGIN = "login"
    LOGOUT = "logout"
    OTHER = "other"
