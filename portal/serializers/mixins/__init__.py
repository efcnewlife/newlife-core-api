"""
Top-level mixins for serializers
"""

from .auth import LoginResponse, LogoutRequest, LogoutResponse, RefreshTokenRequest, TokenResponse
from .base import DeleteBaseModel, DetailQueryModel, GenericQueryBaseModel, OrderByQueryBaseModel, PaginationBaseResponseModel, PaginationQueryBaseModel

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
    "DetailQueryModel",
]
