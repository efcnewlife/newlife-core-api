"""
Admin authentication serializers
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from portal.domain.common.mixins import UUIDModel
from portal.serializers.mixins import LoginResponse


class AdminLoginRequest(BaseModel):
    """Admin login request"""
    email: EmailStr = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")


class AdminInfo(UUIDModel):
    """Admin info"""
    email: str = Field(..., description="Admin email")
    first_name: str = Field(..., description="First name")
    last_name: Optional[str] = Field(..., description="Last name")
    preferred_name: Optional[str] = Field(None, description="Preferred display name", serialization_alias="preferredName")
    roles: list[str] = Field(default_factory=list, description="Admin roles")
    preferred_locale_id: Optional[UUID] = Field(None, description="Preferred locale id", serialization_alias="preferredLocaleId")
    last_login_at: Optional[datetime] = Field(None, description="Last login time")


class AdminLoginResponse(LoginResponse):
    """Admin login response"""
    admin: AdminInfo = Field(..., description="Admin info")


class AdminRequestPasswordResetRequest(BaseModel):
    """Request Password Reset Request"""
    email: EmailStr = Field(..., description="User email address")


class AdminResetPasswordWithTokenRequest(BaseModel):
    """Reset Password With Token Request"""
    token: str = Field(..., description="Password reset token")
    new_password: str = Field(..., min_length=8, description="New password")
    new_password_confirm: str = Field(..., min_length=8, description="New password confirmation")


class MicrosoftIdTokenRequest(BaseModel):
    """Microsoft Entra ID token exchange body"""

    id_token: str = Field(..., description="Microsoft ID token")
