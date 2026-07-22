"""
Room blackout serializers.
"""
from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from portal.domain.facility.constants import DayOfWeek, RoomBlackoutKind
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


class AdminRoomBlackoutQuery(GenericQueryBaseModel):
    """Paginated blackout list filters."""

    facility_id: Optional[UUID] = Field(default=None)


class AdminRoomBlackoutItem(UUIDBaseModel):
    """Blackout item."""

    facility_id: Optional[UUID] = Field(None, serialization_alias="facilityId", description="Room ID; null = all rooms")
    name: str = Field(..., description="Blackout name")
    reason: str = Field(..., description="Admin-only reason")
    kind: str = Field(..., description="one_off or recurring")
    blackout_date: Optional[date] = Field(None, serialization_alias="blackoutDate", description="One-off date")
    days_of_week: Optional[list[int]] = Field(
        None,
        serialization_alias="daysOfWeek",
        description="ISO weekdays 0-6 for recurring",
    )
    start_time: time = Field(..., serialization_alias="startTime", description="Start time")
    end_time: time = Field(..., serialization_alias="endTime", description="End time")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    effective_from: Optional[date] = Field(None, serialization_alias="effectiveFrom", description="Effective from")
    effective_to: Optional[date] = Field(None, serialization_alias="effectiveTo", description="Effective to")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")


class AdminRoomBlackoutPages(PaginationBaseResponseModel):
    """Paginated blackouts."""

    items: list[AdminRoomBlackoutItem] = Field(default_factory=list, description="Items")


class AdminRoomBlackoutList(BaseModel):
    """Blackout list."""

    items: list[AdminRoomBlackoutItem] = Field(default_factory=list, description="Items")


class AdminRoomBlackoutWrite(BaseModel):
    """Blackout write."""

    facility_id: Optional[UUID] = Field(None, description="Room ID; null = all rooms")
    name: str = Field(..., min_length=1, description="Blackout name")
    reason: str = Field(..., min_length=1, description="Admin-only reason")
    kind: str = Field(..., description="one_off or recurring")
    blackout_date: Optional[date] = Field(None, description="One-off date")
    days_of_week: Optional[list[int]] = Field(None, description="ISO weekdays 0-6")
    start_time: time = Field(..., description="Start time")
    end_time: time = Field(..., description="End time")
    is_active: bool = Field(True, description="Active flag")
    effective_from: Optional[date] = Field(None, description="Effective from")
    effective_to: Optional[date] = Field(None, description="Effective to")

    @field_validator("kind")
    @classmethod
    def validate_kind(cls, value: str) -> str:
        normalized = (value or "").strip().lower()
        if normalized not in {RoomBlackoutKind.ONE_OFF.value, RoomBlackoutKind.RECURRING.value}:
            raise ValueError("kind must be one_off or recurring")
        return normalized

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, days: Optional[list[int]]) -> Optional[list[int]]:
        if days is None:
            return None
        return _validate_days_of_week(days)

    @model_validator(mode="after")
    def validate_kind_shape(self) -> "AdminRoomBlackoutWrite":
        if self.kind == RoomBlackoutKind.ONE_OFF.value:
            if self.blackout_date is None:
                raise ValueError("blackout_date is required for one_off")
            if self.days_of_week:
                raise ValueError("days_of_week must be empty for one_off")
        else:
            if self.blackout_date is not None:
                raise ValueError("blackout_date must be empty for recurring")
            if not self.days_of_week:
                raise ValueError("days_of_week is required for recurring")
        if self.start_time >= self.end_time:
            raise ValueError("start_time must be before end_time")
        return self


class AdminRoomBlackoutCreate(AdminRoomBlackoutWrite):
    """Create blackout."""


class AdminRoomBlackoutUpdate(AdminRoomBlackoutWrite):
    """Update blackout."""
