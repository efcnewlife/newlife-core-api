"""
Org position serializers.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.domain.org.constants import PositionOffice, PositionTeam
from portal.serializers.admin.v1.org.translation import (
    AdminPositionTranslationInput,
    AdminPositionTranslationItem,
    validate_unique_position_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminPositionBase(UUIDBaseModel):
    """Position list row."""

    code: str = Field(..., description="Position code")
    team: Optional[PositionTeam] = Field(None, description="Team code")
    office: Optional[PositionOffice] = Field(None, description="Office code")
    name: Optional[str] = Field(None, description="Position name")
    can_own_ministry: bool = Field(False, serialization_alias="canOwnMinistry", description="Can own ministry")
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")


class AdminPositionDetail(AdminPositionBase):
    """Position detail."""

    sequence: Optional[float] = Field(None, description="Sort sequence")
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    translations: list[AdminPositionTranslationItem] = Field(default_factory=list, description="Translations")
    current_user_id: Optional[UUID] = Field(
        None,
        serialization_alias="currentUserId",
        description="Current incumbent user ID",
    )


class AdminPositionPages(PaginationBaseResponseModel):
    """Paginated positions."""

    items: list[AdminPositionDetail] = Field(default_factory=list, description="Items")


class AdminPositionWrite(BaseModel):
    """Position write."""

    team: PositionTeam = Field(..., description="Team code")
    office: PositionOffice = Field(..., description="Office code")
    can_own_ministry: bool = Field(False, description="Can own ministry")
    is_active: bool = Field(True, description="Active flag")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    translations: Optional[list[AdminPositionTranslationInput]] = Field(None, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_position_locale_ids(value)


class AdminPositionCreate(AdminPositionWrite):
    """Create position."""

    code: str = Field(..., description="Position code")


class AdminPositionUpdate(AdminPositionWrite):
    """Update position."""


class AdminPositionBulkAction(BaseModel):
    """Bulk position action."""

    ids: list[UUID] = Field(..., description="Position IDs")


class AdminPositionAssign(BaseModel):
    """Assign position incumbent."""

    user_id: UUID = Field(..., description="Incumbent user ID")
    start_at: Optional[datetime] = Field(None, description="Assignment start")


class AdminAssignablePositionItem(UUIDBaseModel):
    """Assignable position row."""

    code: str = Field(..., description="Position code")
    team: Optional[PositionTeam] = Field(None, description="Team code")
    office: Optional[PositionOffice] = Field(None, description="Office code")
    name: Optional[str] = Field(None, description="Position name")
    incumbent_user_id: Optional[UUID] = Field(
        None,
        serialization_alias="incumbentUserId",
        description="Incumbent user ID",
    )
    incumbent_display_name: Optional[str] = Field(
        None,
        serialization_alias="incumbentDisplayName",
        description="Incumbent display name",
    )


class AdminAssignablePositionList(BaseModel):
    """Assignable positions list."""

    items: list[AdminAssignablePositionItem] = Field(default_factory=list, description="Items")
