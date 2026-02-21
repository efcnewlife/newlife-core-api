"""
Enums for the application - Template: Core enums only
"""
from enum import Enum, IntEnum


class AccessTokenAudType(Enum):
    """Access token audience type"""
    ADMIN = "admin"
    APP = "app"


class AuthProvider(Enum):
    """Third-party authentication provider - extend with providers as needed"""
    pass


class Gender(IntEnum):
    """Gender"""
    UNKNOWN = 0
    MALE = 1
    FEMALE = 2
    OTHER = 3


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
