"""
Admin authentication serializers
"""
from datetime import datetime
from typing import Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str = Field(..., description="Access token", serialization_alias="accessToken")
    refresh_token: str = Field(..., description="Refresh token", serialization_alias="refreshToken")
    token_type: str = Field(default="bearer", description="Token type", serialization_alias="tokenType")
    expires_in: int = Field(..., description="Access token expiration (seconds)", serialization_alias="expiresIn")


class LoginResponse(BaseModel):
    """Admin login response"""
    token: TokenResponse = Field(..., description="Auth token")


class AdminPrincipalResponse(BaseModel):
    """Admin user summary returned on login and /auth/me"""
    model_config = ConfigDict(populate_by_name=True)

    id: str = Field(..., description="User id")
    email: str = Field(..., description="Email")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    roles: list[str] = Field(default_factory=list, description="Role codes")
    last_login_at: Optional[datetime] = Field(None, description="Last login time", serialization_alias="lastLoginAt")


class AdminLoginSuccessResponse(BaseModel):
    """Admin login: same shape as portal frontend AdminLoginResponse"""
    model_config = ConfigDict(populate_by_name=True)

    admin: AdminPrincipalResponse = Field(..., description="Admin user")
    token: TokenResponse = Field(..., description="Auth token")


class AdminPasswordLoginRequest(BaseModel):
    """Email/password login body"""
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(..., description="Email")
    password: str = Field(..., description="Password")


class MicrosoftIdTokenRequest(BaseModel):
    """Microsoft Entra ID token exchange body"""
    model_config = ConfigDict(populate_by_name=True)

    id_token: str = Field(
        ...,
        description="Microsoft ID token",
        validation_alias=AliasChoices("id_token", "idToken"),
        serialization_alias="idToken",
    )


class RefreshTokenRequest(BaseModel):
    """Refresh token request"""
    model_config = ConfigDict(populate_by_name=True)

    refresh_token: str = Field(
        ...,
        description="Refresh token",
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )


class LogoutRequest(BaseModel):
    """Logout request"""
    model_config = ConfigDict(populate_by_name=True)

    access_token: str = Field(
        ...,
        description="Access token to blacklist",
        validation_alias=AliasChoices("access_token", "accessToken"),
        serialization_alias="accessToken",
    )
    refresh_token: Optional[str] = Field(
        None,
        description="Refresh token to blacklist",
        validation_alias=AliasChoices("refresh_token", "refreshToken"),
        serialization_alias="refreshToken",
    )


class LogoutResponse(BaseModel):
    """Logout response"""
    message: str = Field(..., description="Logout message")
