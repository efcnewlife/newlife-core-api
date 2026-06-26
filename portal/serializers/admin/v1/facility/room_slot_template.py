"""
Room slot template serializers.
"""
from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.domain.facility.constants import DayOfWeek
from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


def _validate_days_of_week(days: list[int]) -> list[int]:
    if not days:
        raise ValueError("days_of_week must contain at least one weekday")
    unique_days = sorted(set(days))
    for day in unique_days:
        if day < DayOfWeek.MONDAY or day > DayOfWeek.SUNDAY:
            raise ValueError(f"each weekday must be between {DayOfWeek.MONDAY} and {DayOfWeek.SUNDAY}")
    return unique_days


class AdminRoomSlotTemplateQuery(GenericQueryBaseModel):
    """Paginated slot template list filters."""

    facility_id: Optional[UUID] = Field(default=None)


class AdminRoomSlotTemplateItem(UUIDBaseModel):
    """Slot template item."""

    facility_id: UUID = Field(..., serialization_alias="facilityId", description="Room ID")
    name: str = Field(..., description="Template name")
    days_of_week: list[int] = Field(
        ...,
        serialization_alias="daysOfWeek",
        description="ISO weekdays 0-6 (Monday-Sunday)",
    )
    start_time: time = Field(..., serialization_alias="startTime", description="Start time")
    end_time: time = Field(..., serialization_alias="endTime", description="End time")
    slot_duration_minutes: int = Field(..., serialization_alias="slotDurationMinutes", description="Slot duration")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    effective_from: Optional[date] = Field(None, serialization_alias="effectiveFrom", description="Effective from")
    effective_to: Optional[date] = Field(None, serialization_alias="effectiveTo", description="Effective to")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")


class AdminRoomSlotTemplatePages(PaginationBaseResponseModel):
    """Paginated slot templates."""

    items: list[AdminRoomSlotTemplateItem] = Field(default_factory=list, description="Items")


class AdminRoomSlotTemplateList(BaseModel):
    """Slot template list."""

    items: list[AdminRoomSlotTemplateItem] = Field(default_factory=list, description="Items")


class AdminRoomSlotTemplateWrite(BaseModel):
    """Slot template write."""

    facility_id: UUID = Field(..., description="Room ID")
    name: str = Field(..., description="Template name")
    days_of_week: list[int] = Field(..., min_length=1, description="ISO weekdays 0-6")
    start_time: time = Field(..., description="Start time")
    end_time: time = Field(..., description="End time")
    slot_duration_minutes: int = Field(..., description="Slot duration")
    is_active: bool = Field(True, description="Active flag")
    effective_from: Optional[date] = Field(None, description="Effective from")
    effective_to: Optional[date] = Field(None, description="Effective to")

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, days: list[int]) -> list[int]:
        return _validate_days_of_week(days)


class AdminRoomSlotTemplateCreate(AdminRoomSlotTemplateWrite):
    """Create slot template."""


class AdminRoomSlotTemplateUpdate(AdminRoomSlotTemplateWrite):
    """Update slot template."""
