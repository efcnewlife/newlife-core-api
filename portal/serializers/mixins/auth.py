"""
Admin authentication serializers
"""
from typing import Optional

from pydantic import BaseModel, Field


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str = Field(..., description="Access token", serialization_alias="accessToken")
    refresh_token: str = Field(..., description="Refresh token", serialization_alias="refreshToken")
    token_type: str = Field(default="bearer", description="Token type", serialization_alias="tokenType")
    expires_in: int = Field(..., description="Access token expiration (seconds)", serialization_alias="expiresIn")


class LoginResponse(BaseModel):
    """Admin login response"""
    token: TokenResponse = Field(..., description="Auth token")


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str = Field(..., description="Refresh token", serialization_alias="refreshToken")


class LogoutRequest(BaseModel):
    """Logout request"""
    access_token: str = Field(..., description="Access token to blacklist")
    refresh_token: Optional[str] = Field(None, description="Refresh token to blacklist")


class LogoutResponse(BaseModel):
    """Logout response"""
    message: str = Field(..., description="Logout message")
