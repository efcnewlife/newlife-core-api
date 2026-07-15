"""
Ministry admin API serializers.
"""
from datetime import date, datetime, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.domain.facility.constants import DayOfWeek
from portal.domain.org.constants import MinistryMemberRole
from portal.serializers.admin.v1.ministry_catalog import AdminMinistryTypeItem, AdminTargetAudienceItem
from portal.serializers.admin.v1.org.translation import (
    AdminOrgTranslationInput,
    AdminOrgTranslationItem,
    validate_unique_org_locale_ids,
)
from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


def _validate_optional_days_of_week(days: list[int]) -> list[int]:
    if not days:
        return days
    unique_days = sorted(set(days))
    for day in unique_days:
        if day < DayOfWeek.MONDAY or day > DayOfWeek.SUNDAY:
            raise ValueError(f"each weekday must be between {DayOfWeek.MONDAY} and {DayOfWeek.SUNDAY}")
    return unique_days


class AdminMinistryScheduleInput(BaseModel):
    """Ministry schedule input."""

    days_of_week: list[int] = Field(default_factory=list, description="ISO weekdays 0-6")
    start_time: Optional[time] = Field(default=None, description="Start time")
    end_time: Optional[time] = Field(default=None, description="End time")
    effective_from: Optional[date] = Field(default=None, description="Effective from")
    effective_to: Optional[date] = Field(default=None, description="Effective to")
    sequence: Optional[float] = Field(default=None, description="Sort sequence")

    @field_validator("days_of_week")
    @classmethod
    def validate_days_of_week(cls, days: list[int]) -> list[int]:
        return _validate_optional_days_of_week(days)


class AdminMinistryScheduleItem(BaseModel):
    """Ministry schedule response item."""

    id: Optional[UUID] = Field(default=None, description="Schedule ID")
    days_of_week: list[int] = Field(
        default_factory=list,
        serialization_alias="daysOfWeek",
        description="ISO weekdays 0-6",
    )
    start_time: Optional[time] = Field(None, serialization_alias="startTime", description="Start time")
    end_time: Optional[time] = Field(None, serialization_alias="endTime", description="End time")
    effective_from: Optional[date] = Field(None, serialization_alias="effectiveFrom", description="Effective from")
    effective_to: Optional[date] = Field(None, serialization_alias="effectiveTo", description="Effective to")
    sequence: Optional[float] = Field(None, description="Sort sequence")


class AdminMinistryMemberInput(BaseModel):
    """Ministry member input."""

    user_id: UUID = Field(..., description="Member user ID")
    member_role: MinistryMemberRole = Field(..., description="Member role")
    remark: Optional[str] = Field(default=None, description="Member remark")
    contact_email: Optional[str] = Field(default=None, description="Public contact email override")


class AdminMinistryMemberItem(BaseModel):
    """Ministry member response item."""

    user_id: UUID = Field(..., serialization_alias="userId", description="Member user ID")
    member_role: str = Field(..., serialization_alias="memberRole", description="Member role")
    email: Optional[str] = Field(None, description="Member email")
    display_name: Optional[str] = Field(None, serialization_alias="displayName", description="Member display name")
    remark: Optional[str] = Field(default=None, description="Member remark")
    contact_email: Optional[str] = Field(
        None,
        serialization_alias="contactEmail",
        description="Public contact email override",
    )


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
    ministry_type: Optional[AdminMinistryTypeItem] = Field(
        None,
        serialization_alias="ministryType",
        description="Ministry type",
    )
    target_audiences: list[AdminTargetAudienceItem] = Field(
        default_factory=list,
        serialization_alias="targetAudiences",
        description="Target audiences",
    )


class AdminMinistryDetail(AdminMinistryBase):
    """Ministry detail."""

    owner_position_id: Optional[UUID] = Field(
        None,
        serialization_alias="ownerPositionId",
        description="Owning position ID",
    )
    ministry_type_id: Optional[UUID] = Field(
        None,
        serialization_alias="ministryTypeId",
        description="Ministry type ID",
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
    target_audiences: list[AdminTargetAudienceItem] = Field(
        default_factory=list,
        serialization_alias="targetAudiences",
        description="Target audiences",
    )
    schedules: list[AdminMinistryScheduleItem] = Field(default_factory=list, description="Schedules")


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
    ministry_type_id: Optional[UUID] = Field(None, description="Ministry type ID")
    target_audience_ids: Optional[list[UUID]] = Field(default=None, description="Target audience IDs")
    schedules: Optional[list[AdminMinistryScheduleInput]] = Field(default=None, description="Schedules")
    has_priority_booking: bool = Field(False, description="Priority booking flag")
    is_active: bool = Field(True, description="Active flag")
    sequence: Optional[float] = Field(None, description="Sort sequence")
    translations: Optional[list[AdminOrgTranslationInput]] = Field(None, description="Translations")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        return validate_unique_org_locale_ids(value)

    @field_validator("target_audience_ids")
    @classmethod
    def validate_target_audience_ids(cls, value: Optional[list[UUID]]) -> Optional[list[UUID]]:
        if value is None:
            return value
        if len(value) != len(set(value)):
            raise ValueError("Duplicate target_audience_id")
        return value


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
