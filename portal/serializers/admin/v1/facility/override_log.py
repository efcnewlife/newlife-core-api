"""
Admin booking override log serializers.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminOverrideLogQuery(GenericQueryBaseModel):
    """Override log filters."""

    facility_id: Optional[UUID] = Field(default=None)
    overridden_by_id: Optional[UUID] = Field(default=None)
    date_from: Optional[datetime] = Field(default=None)
    date_to: Optional[datetime] = Field(default=None)


class AdminOverrideLogItem(UUIDBaseModel):
    """Override log row."""

    facility_booking_id: UUID = Field(..., serialization_alias="facilityBookingId")
    overridden_booking_id: Optional[UUID] = Field(default=None, serialization_alias="overriddenBookingId")
    overridden_by_id: UUID = Field(..., serialization_alias="overriddenById")
    overridden_by_name: Optional[str] = Field(default=None, serialization_alias="overriddenByName")
    facility_id: UUID = Field(..., serialization_alias="facilityId")
    facility_name: Optional[str] = Field(default=None, serialization_alias="facilityName")
    outcome: str = Field(...)
    reason: Optional[str] = Field(default=None)
    created_at: datetime = Field(..., serialization_alias="createdAt")
    created_by: Optional[str] = Field(default=None, serialization_alias="createdBy")


class AdminOverrideLogPages(PaginationBaseResponseModel):
    """Paginated override logs."""

    items: list[AdminOverrideLogItem] = Field(default_factory=list)
