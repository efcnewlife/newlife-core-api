"""
Auth domain entities.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field

from portal.domain.common.mixins import UUIDModel
from portal.libs.consts.enums import Gender


class User(UUIDModel):
    """Core user account with profile fields."""

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
