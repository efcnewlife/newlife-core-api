"""
Admin authentication serializers
"""
from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field

from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import LoginResponse


class AdminLoginRequest(BaseModel):
    """Admin login request"""
    email: EmailStr = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")


class AdminInfo(UUIDBaseModel):
    """Admin info"""
    email: str = Field(..., description="Admin email")
    first_name: str = Field(..., description="First name")
    last_name: Optional[str] = Field(..., description="Last name")
    roles: list[str] = Field(default_factory=list, description="Admin roles")
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
    model_config = ConfigDict(populate_by_name=True)

    id_token: str = Field(
        ...,
        description="Microsoft ID token",
        validation_alias=AliasChoices("id_token", "idToken"),
        serialization_alias="idToken",
    )
