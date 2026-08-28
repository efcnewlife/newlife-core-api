"""
Member-facing ministry approval API serializers.
"""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from portal.serializers.admin.v1.ministry import AdminMinistryApprove, AdminMinistryMemberInput, AdminMinistryReject
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


ApiMinistryApprove = AdminMinistryApprove
ApiMinistryReject = AdminMinistryReject
