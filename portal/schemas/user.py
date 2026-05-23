"""
Schema of User model (backward-compatible re-exports).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from portal.application.auth.results import UserDetail, UserSensitive
from portal.domain.common.mixins import UUIDModel
from portal.libs.consts.enums import Gender

SUserDetail = UserDetail
SUserSensitive = UserSensitive


class SUserThirdParty(UserDetail):
    """Third-party linked user schema."""

    provider_id: UUID = Field(..., description="Provider ID", frozen=True, exclude=True)
    provider: str = Field(..., description="Provider name", frozen=True, exclude=True)
    provider_uid: str = Field(..., description="Provider UID", frozen=True, exclude=True)
    additional_data: Optional[dict] = Field(
        None,
        description="Additional Data from the provider",
        frozen=True,
        exclude=True,
    )

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


class SAuthProvider(UUIDModel):
    """Schema for Auth Provider."""

    name: str = Field(..., description="Provider name")
