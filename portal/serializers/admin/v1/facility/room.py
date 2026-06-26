"""
Facility room serializers.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.serializers.admin.v1.facility.translation import (
    AdminFacilityTranslationInput,
    AdminFacilityTranslationItem,
    validate_unique_facility_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminRoomBase(UUIDBaseModel):
    """Room base."""

    code: str = Field(..., description="Room code")
    name: Optional[str] = Field(None, description="Room name")


class AdminRoomItem(AdminRoomBase):
    """Room list item."""

    room_number: Optional[str] = Field(None, serialization_alias="roomNumber", description="Room number")
    capacity: Optional[int] = Field(None, description="Capacity")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")
    sequence: Optional[float] = Field(None, description="Sort sequence")


class AdminRoomDetail(AdminRoomItem):
    """Room detail."""

    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    description: Optional[str] = Field(None, description="Description")
    translations: list[AdminFacilityTranslationItem] = Field(default_factory=list, description="Translations")


class AdminRoomPages(PaginationBaseResponseModel):
    """Paginated rooms."""

    items: list[AdminRoomDetail] = Field(default_factory=list, description="Room items")


class AdminRoomList(BaseModel):
    """Room dropdown list."""

    items: list[AdminRoomBase] = Field(default_factory=list, description="Room items")


class AdminRoomWrite(BaseModel):
    """Room write payload."""

    name: Optional[str] = Field(None, description="Room name")
    room_number: Optional[str] = Field(None, description="Room number")
    capacity: Optional[int] = Field(None, description="Capacity")
    is_active: bool = Field(True, description="Active flag")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    translations: Optional[list[AdminFacilityTranslationInput]] = Field(None, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_facility_locale_ids(value)


class AdminRoomCreate(AdminRoomWrite):
    """Create room."""

    code: str = Field(..., description="Room code")
    translations: list[AdminFacilityTranslationInput] = Field(..., min_length=1, description="Translations")


class AdminRoomUpdate(AdminRoomWrite):
    """Update room (code immutable)."""


class AdminRoomBulkAction(BaseModel):
    """Bulk room action."""

    ids: list[UUID] = Field(..., description="Room IDs")
