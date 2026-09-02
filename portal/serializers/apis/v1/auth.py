"""
Member authentication serializers.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.common.mixins import UUIDModel
from portal.serializers.mixins import LoginResponse, TokenResponse


class MemberInfo(UUIDModel):
    """Member profile for SPA responses."""

    email: str = Field(..., description="Member email")
    first_name: str = Field(..., description="First name")
    last_name: Optional[str] = Field(None, description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred display name", serialization_alias="preferredName")
    roles: list[str] = Field(default_factory=list, description="Roles")
    preferred_locale_id: Optional[UUID] = Field(None, description="Preferred locale id", serialization_alias="preferredLocaleId")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")


class MemberLoginResponse(LoginResponse):
    """Member login response."""

    member: MemberInfo = Field(..., description="Member info")


class MicrosoftIdTokenRequest(BaseModel):
    """Microsoft Entra ID token exchange body."""

    id_token: str = Field(..., description="Microsoft ID token")


class MockLoginRequest(BaseModel):
    """Mock login body for dev/staging testing accounts."""

    email: str = Field(..., description="Testing account email")
