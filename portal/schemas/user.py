"""
Schema of User model.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from portal.libs.consts.enums import Gender
from portal.schemas.mixins import UUIDBaseModel, BaseMixinModel


class SUserBase(UUIDBaseModel, BaseMixinModel):
    """
    Base schema for User model, containing common fields.
    """
    email: str = Field(None, description="User's email address")
    verified: bool = Field(False, description="Is the user verified")
    is_active: bool = Field(description="Is the user active")
    is_superuser: bool = Field(False, description="Is the user a superuser")
    is_admin: bool = Field(False, description="Can the user access the admin panel")
    phone_number: Optional[str] = Field(None, description="User's phone number")
    last_login_at: Optional[datetime] = Field(None, description="Timestamp of the user's last login")


class SUserDetail(SUserBase):
    """
    Detailed schema for User model, extending UserBase with additional fields.
    """
    first_name: str = Field(None, description="User's first name")
    last_name: str = Field(None, description="User's last name")
    preferred_name: Optional[str] = Field(None, description="User's preferred name")
    gender: Optional[Gender] = Field(None, description="User's gender")


class SUserSensitive(SUserDetail):
    """
    Schema for User model including sensitive fields.
    """
    password_hash: Optional[str] = Field(None, description="Hashed password for the user", exclude=True)
    salt: Optional[str] = Field(None, description="Salt used for hashing the password", exclude=True)
    password_changed_at: Optional[datetime] = Field(None, description="Timestamp of the user's password last change", exclude=True)
    password_expires_at: Optional[datetime] = Field(None, description="Timestamp of the user's password expiration", exclude=True)


class SUserThirdParty(SUserDetail):
    provider_id: UUID = Field(..., description="Provider ID", frozen=True, exclude=True)
    provider: str = Field(..., description="Provider name", frozen=True, exclude=True)
    provider_uid: str = Field(..., description="Provider UID", frozen=True, exclude=True)
    additional_data: Optional[dict] = Field(None, description="Additional Data from the provider", frozen=True, exclude=True)

    @field_validator("additional_data", mode="before")
    @classmethod
    def serialize_additional_data(cls, value: Optional[str]) -> Optional[dict]:
        """
        Validate and serialize additional_data field.

        :param value:
        :return:
        """
        if isinstance(value, str):
            import ujson
            try:
                value = ujson.loads(value)
            except ujson.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON string for additional_data: {e}")
        return value


class SAuthProvider(UUIDBaseModel):
    """
    Schema for Auth Provider
    """
    name: str = Field(..., description="Provider name")
