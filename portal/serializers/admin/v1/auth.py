"""
Admin authentication serializers
"""
from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, Field

from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import LoginResponse


class AdminLoginRequest(BaseModel):
    """Admin login request"""
    email: EmailStr = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")
    gac: Optional[str] = Field(None, description="Google Authenticator code")


class AdminInfo(UUIDBaseModel):
    """Admin info"""
    email: str = Field(..., description="Admin email")
    display_name: str = Field(..., description="Display name")
    roles: List[str] = Field(default=[], description="Admin roles")
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
