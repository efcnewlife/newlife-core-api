"""
Ministry admin API serializers.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.domain.org.constants import MinistryMemberRole
from portal.serializers.admin.v1.org.translation import (
    AdminOrgTranslationInput,
    AdminOrgTranslationItem,
    validate_unique_org_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminMinistryMemberInput(BaseModel):
    """Ministry member input."""

    user_id: UUID = Field(..., description="Member user ID")
    member_role: MinistryMemberRole = Field(..., description="Member role")
    remark: Optional[str] = Field(default=None, description="Member remark")


class AdminMinistryMemberItem(BaseModel):
    """Ministry member response item."""

    user_id: UUID = Field(..., serialization_alias="userId", description="Member user ID")
    member_role: str = Field(..., serialization_alias="memberRole", description="Member role")
    email: Optional[str] = Field(None, description="Member email")
    display_name: Optional[str] = Field(None, serialization_alias="displayName", description="Member display name")
    remark: Optional[str] = Field(default=None, description="Member remark")


class AdminMinistryBase(UUIDBaseModel):
    """Ministry list row."""

    name: Optional[str] = Field(None, description="Ministry name")
    status: str = Field(..., description="Lifecycle status")
    has_priority_booking: bool = Field(
        False,
        serialization_alias="hasPriorityBooking",
        description="Priority booking flag",
    )
    is_active: bool = Field(True, serialization_alias="isActive", description="Active flag")


class AdminMinistryDetail(AdminMinistryBase):
    """Ministry detail."""

    owner_position_id: Optional[UUID] = Field(
        None,
        serialization_alias="ownerPositionId",
        description="Owning position ID",
    )
    sequence: Optional[float] = Field(None, description="Sort sequence")
    submitted_at: Optional[datetime] = Field(None, serialization_alias="submittedAt", description="Submitted at")
    submitted_by_id: Optional[UUID] = Field(None, serialization_alias="submittedById", description="Submitted by")
    approved_at: Optional[datetime] = Field(None, serialization_alias="approvedAt", description="Approved at")
    approved_by_id: Optional[UUID] = Field(None, serialization_alias="approvedById", description="Approved by")
    rejected_at: Optional[datetime] = Field(None, serialization_alias="rejectedAt", description="Rejected at")
    rejected_by_id: Optional[UUID] = Field(None, serialization_alias="rejectedById", description="Rejected by")
    rejection_reason: Optional[str] = Field(
        None,
        serialization_alias="rejectionReason",
        description="Rejection reason",
    )
    created_at: Optional[datetime] = Field(None, serialization_alias="createAt", description="Created at")
    created_by: Optional[str] = Field(None, serialization_alias="createdBy", description="Created by")
    updated_at: Optional[datetime] = Field(None, serialization_alias="updateAt", description="Updated at")
    updated_by: Optional[str] = Field(None, serialization_alias="updatedBy", description="Updated by")
    delete_reason: Optional[str] = Field(None, serialization_alias="deleteReason", description="Delete reason")
    translations: list[AdminOrgTranslationItem] = Field(default_factory=list, description="Translations")
    members: list[AdminMinistryMemberItem] = Field(default_factory=list, description="Ministry members")


class AdminMinistryPages(PaginationBaseResponseModel):
    """Paginated ministries."""

    items: list[AdminMinistryDetail] = Field(default_factory=list, description="Items")


class AdminMinistryList(BaseModel):
    """Ministry dropdown list."""

    items: list[AdminMinistryBase] = Field(default_factory=list, description="Items")


class AdminMinistryWrite(BaseModel):
    """Ministry write."""

    name: Optional[str] = Field(None, description="Ministry name")
    owner_position_id: Optional[UUID] = Field(None, description="Owning position ID")
    has_priority_booking: bool = Field(False, description="Priority booking flag")
    is_active: bool = Field(True, description="Active flag")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    translations: Optional[list[AdminOrgTranslationInput]] = Field(None, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_org_locale_ids(value)


class AdminMinistryCreate(AdminMinistryWrite):
    """Create ministry."""

    translations: list[AdminOrgTranslationInput] = Field(..., min_length=1, description="Translations")


class AdminMinistryUpdate(AdminMinistryWrite):
    """Update ministry."""


class AdminMinistryBulkAction(BaseModel):
    """Bulk ministry action."""

    ids: list[UUID] = Field(..., description="Ministry IDs")


class AdminMinistryReplaceMembers(BaseModel):
    """Replace ministry members."""

    members: list[AdminMinistryMemberInput] = Field(default_factory=list, description="Ministry members")


class AdminMinistryReject(BaseModel):
    """Reject ministry."""

    rejection_reason: str = Field(..., description="Rejection reason")
    comment: Optional[str] = Field(None, description="Comment")


class AdminMinistryApprove(BaseModel):
    """Approve ministry."""

    comment: Optional[str] = Field(None, description="Comment")


class AdminMinistryApplicationCreate(BaseModel):
    """Create and submit ministry application."""

    owner_position_id: UUID = Field(..., description="Owning position ID")
    has_priority_booking: bool = Field(False, description="Priority booking flag")
    translations: list[AdminOrgTranslationInput] = Field(default_factory=list, description="Translations")
    members: list[AdminMinistryMemberInput] = Field(default_factory=list, description="Ministry members")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_org_locale_ids(value)
