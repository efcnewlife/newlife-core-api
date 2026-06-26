"""
Auth application commands.
"""
from uuid import UUID

from pydantic import BaseModel, Field


class LoginCommand(BaseModel):
    """Password login command."""

    email: str = Field(..., description="Admin email")
    password: str = Field(..., description="Admin password")


class LoginWithoutValidateCommand(BaseModel):
    """Dev-only login command that skips password validation."""

    email: str = Field(..., description="Admin email")


class RefreshTokenCommand(BaseModel):
    """Refresh access token command."""

    refresh_token: str = Field(..., description="Opaque refresh token")


class MicrosoftLoginCommand(BaseModel):
    """Microsoft Entra ID login command."""

    id_token: str = Field(..., description="Microsoft ID token")


class LogoutCommand(BaseModel):
    """Logout command."""

    access_token: str = Field(..., description="Access token to blacklist")
    refresh_token: str | None = Field(None, description="Refresh token to revoke")
