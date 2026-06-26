"""
Auth application read models and token payloads.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from portal.domain.common.mixins import UUIDBaseModel
from portal.libs.consts.enums import Gender


class HeaderInfo(BaseModel):
    """HTTP header snapshot for request context."""

    user_agent: Optional[str] = Field(None, description="User-Agent")
    accept_language: Optional[str] = Field(None, description="Accept-Language")
    host: Optional[str] = Field(None, description="Host")
    referer: Optional[str] = Field(None, description="Referer")
    origin: Optional[str] = Field(None, description="Origin")


class TokenPayload(BaseModel):
    """JWT token payload base."""

    sub: UUID = Field(..., description="Subject. Unique identifier for the user")
    exp: int = Field(..., description="Expiration time")
    aud: str = Field(..., description="Audience")
    iat: int = Field(..., description="Issued at")
    iss: str = Field(..., description="Issuer")
    user_id: UUID = Field(..., description="User ID")

    @field_serializer("user_id")
    def serialize_uuid(self, value: UUID, _info) -> str:
        return str(value)


class AccessTokenPayload(TokenPayload):
    """Access token JWT payload."""

    email: str = Field(..., description="Email")
    first_name: str = Field(None, description="User's first name")
    last_name: str = Field(None, description="User's last name")
    preferred_name: Optional[str] = Field(None, description="User's preferred name")
    roles: Optional[list] = Field(None, description="Roles")
    scope: str = Field(None, description="scope(permissions)")
    family_id: UUID = Field(..., description="Refresh token family id")


class RefreshTokenData(UUIDBaseModel):
    """Opaque refresh token metadata for provider operations."""

    user_id: UUID = Field(..., description="User ID")
    device_id: UUID = Field(..., description="Device ID")
    family_id: UUID = Field(..., description="Family ID")
    parent_id: Optional[UUID] = Field(None, description="Parent ID")
    replaced_by_id: Optional[UUID] = Field(None, description="Replaced by ID")
    token_hash: str = Field(..., description="Token hash")
    expires_at: datetime = Field(..., description="Expires at")
    last_used_at: datetime = Field(..., description="Last used at")
    revoked_at: Optional[datetime] = Field(None, description="Revoked at")
    revoked_reason: Optional[str] = Field(None, description="Revoked reason")
    ip: Optional[str] = Field(None, description="IP")
    user_agent: Optional[str] = Field(None, description="User agent")


class UserDetail(UUIDBaseModel):
    """User detail for token validation and public auth context."""

    email: Optional[str] = Field(default=None, description="User email address")
    verified: bool = Field(default=False, description="Whether the user is verified")
    is_active: bool = Field(default=True, description="Whether the user is active")
    is_superuser: bool = Field(default=False, description="Whether the user is a superuser")
    is_admin: bool = Field(default=False, description="Whether the user can access admin portal")
    phone_number: Optional[str] = Field(default=None, description="User phone number")
    last_login_at: Optional[datetime] = Field(default=None, description="Last login timestamp")
    first_name: Optional[str] = Field(default=None, description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    preferred_name: Optional[str] = Field(default=None, description="Preferred display name")
    preferred_locale_id: Optional[UUID] = Field(default=None, description="Preferred locale id")
    gender: Optional[Gender] = Field(default=None, description="Gender")


class UserSensitive(UserDetail):
    """User detail including sensitive auth fields."""

    password_hash: Optional[str] = Field(default=None, description="Hashed password", exclude=True)
    salt: Optional[str] = Field(default=None, description="Password salt", exclude=True)
    password_changed_at: Optional[datetime] = Field(default=None, description="Password changed at", exclude=True)
    password_expires_at: Optional[datetime] = Field(default=None, description="Password expires at", exclude=True)


class TokenResult(BaseModel):
    """Issued token pair for admin auth."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="Opaque refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token lifetime in seconds")


class AdminProfileResult(UUIDBaseModel):
    """Authenticated admin profile."""

    email: str = Field(..., description="Admin email")
    first_name: str = Field(..., description="First name")
    last_name: Optional[str] = Field(default=None, description="Last name")
    preferred_name: Optional[str] = Field(default=None, description="Preferred display name")
    roles: list[str] = Field(default_factory=list, description="Admin roles")
    preferred_locale_id: Optional[UUID] = Field(default=None, description="Preferred locale id")
    last_login_at: Optional[datetime] = Field(default=None, description="Last login time")


class LoginResult(BaseModel):
    """Admin login outcome."""

    admin: AdminProfileResult = Field(..., description="Admin profile")
    token: TokenResult = Field(..., description="Issued tokens")
