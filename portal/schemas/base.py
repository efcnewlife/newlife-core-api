"""
Basic schemas
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_serializer

from .mixins import UUIDBaseModel


class TokenPayload(BaseModel):
    """Token Payload"""
    sub: UUID = Field(..., description="Subject. Unique identifier for the user")
    exp: int = Field(..., description="Expiration time")
    aud: str = Field(..., description="Audience")
    iat: int = Field(..., description="Issued at")
    iss: str = Field(..., description="Issuer")
    user_id: UUID = Field(..., description="User ID")

    @field_serializer("user_id")
    def serialize_uuid(self, value: UUID, _info) -> str:
        """

        :param value:
        :param _info:
        :return:
        """
        return str(value)


class AccessTokenPayload(TokenPayload):
    """Access Token Payload"""
    email: str = Field(..., description="Email")
    display_name: str = Field(..., description="Display name")
    roles: Optional[list] = Field(None, description="Roles")
    scope: str = Field(None, description="scope(permissions)")
    family_id: UUID = Field(..., description="Refresh token family id")


class RefreshTokenData(UUIDBaseModel):
    """Opaque Refresh Token Data for provider operations"""
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
