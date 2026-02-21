"""
Top-level mixins for serializers
"""
from .auth import (
    TokenResponse,
    LoginResponse,
    RefreshTokenRequest,
    LogoutRequest,
    LogoutResponse
)
from .base import (
    PaginationQueryBaseModel,
    OrderByQueryBaseModel,
    GenericQueryBaseModel,
    PaginationBaseResponseModel,
    DeleteBaseModel,
)

__all__ = [
    # auth
    "TokenResponse",
    "LoginResponse",
    "RefreshTokenRequest",
    "LogoutRequest",
    "LogoutResponse",
    # base
    "PaginationQueryBaseModel",
    "OrderByQueryBaseModel",
    "GenericQueryBaseModel",
    "PaginationBaseResponseModel",
    "DeleteBaseModel",
]
