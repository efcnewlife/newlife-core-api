"""
Member-facing ministry approval API serializers.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.serializers.admin.v1.ministry import AdminMinistryApprove, AdminMinistryMemberInput, AdminMinistryReject
from portal.serializers.admin.v1.ministry_catalog import AdminTargetAudienceItem
from portal.serializers.admin.v1.org.translation import AdminOrgTranslationInput, validate_unique_org_locale_ids
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class ApiRejectedMinistryApplicationUpdate(BaseModel):
    """Update a rejected ministry application (owner position is locked)."""

    ministry_type_id: Optional[UUID] = Field(None, description="Ministry type ID")
    target_audience_ids: Optional[list[UUID]] = Field(None, description="Target audience IDs")
    has_priority_booking: bool = Field(False, description="Priority booking flag")
    translations: Optional[list[AdminOrgTranslationInput]] = Field(None, description="Translations")
    members: Optional[list[AdminMinistryMemberInput]] = Field(None, description="Ministry members")

    @field_validator("translations")
    @classmethod
    def validate_translations(cls, value):
        if value is None:
            return value
        return validate_unique_org_locale_ids(value)


class ApiMinistryApprovalPendingItem(UUIDBaseModel):
    """Pending ministry application awaiting incumbent decision."""

    name: Optional[str] = Field(None, description="Ministry name")
    status: str = Field(..., description="Lifecycle status")
    has_priority_booking: bool = Field(False, serialization_alias="hasPriorityBooking", description="Priority booking flag")


class ApiMinistryApprovalPendingList(BaseModel):
    """Pending approvals for the current incumbent."""

    items: list[ApiMinistryApprovalPendingItem] = Field(default_factory=list, description="Items")


class ApiMinistryProfileSteward(BaseModel):
    """Steward display row on member Ministry Profile."""

    member_role: str = Field(..., serialization_alias="memberRole", description="Steward role")
    display_name: Optional[str] = Field(None, serialization_alias="displayName", description="Steward display name")
    email: Optional[str] = Field(None, description="Steward contact email")


class ApiMinistryProfileOwnerPosition(BaseModel):
    """Localized Owner Position with live incumbent contact."""

    name: Optional[str] = Field(None, description="Localized Owner Position name")
    incumbent_display_name: Optional[str] = Field(None, serialization_alias="incumbentDisplayName", description="Current incumbent display name")
    incumbent_email: Optional[str] = Field(None, serialization_alias="incumbentEmail", description="Current incumbent email")


class ApiMinistryProfile(UUIDBaseModel):
    """Member-facing Ministry Profile projection."""

    name: Optional[str] = Field(None, description="Localized Ministry name")
    purpose: Optional[str] = Field(None, description="Localized Ministry purpose")
    status: str = Field(..., description="Lifecycle status")
    has_priority_booking: bool = Field(False, serialization_alias="hasPriorityBooking", description="Priority booking flag")
    submitted_at: Optional[datetime] = Field(None, serialization_alias="submittedAt", description="Submitted at")
    approved_at: Optional[datetime] = Field(None, serialization_alias="approvedAt", description="Approved at")
    rejected_at: Optional[datetime] = Field(None, serialization_alias="rejectedAt", description="Rejected at")
    rejection_reason: Optional[str] = Field(None, serialization_alias="rejectionReason", description="Rejection reason")
    target_audiences: list[AdminTargetAudienceItem] = Field(default_factory=list, serialization_alias="targetAudiences", description="Target audiences")
    stewards: list[ApiMinistryProfileSteward] = Field(default_factory=list, description="Steward roster")
    owner_position: Optional[ApiMinistryProfileOwnerPosition] = Field(
        None, serialization_alias="ownerPosition", description="Owner Position with live incumbent contact"
    )


ApiMinistryApprove = AdminMinistryApprove
ApiMinistryReject = AdminMinistryReject
