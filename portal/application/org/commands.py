"""
Organization application commands.
"""
from datetime import datetime
from datetime import date, time
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from portal.application.rbac.commands import BulkIdsCommand, DeleteCommand, PagesQueryCommand
from portal.domain.org.constants import MinistryMemberRole, PositionOffice, PositionTeam

__all__ = [
    "ApproveMinistryCommand",
    "AssignPositionCommand",
    "BulkIdsCommand",
    "CreateMemberPersonCommand",
    "CreateMinistryCommand",
    "CreatePositionCommand",
    "DeleteCommand",
    "LinkMemberPersonCommand",
    "MinistryApplicationCommand",
    "MinistryMemberEntryCommand",
    "MinistryScheduleCommand",
    "OrgTranslationCommand",
    "PagesQueryCommand",
    "PositionTranslationCommand",
    "RejectMinistryCommand",
    "ReplaceMinistryMembersCommand",
    "SubmitMinistryCommand",
    "UpdateMemberPersonCommand",
    "UpdateMinistryCommand",
    "UpdatePositionCommand",
]


class OrgTranslationCommand(BaseModel):
    """Localized org ministry content."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)
    schedule_note: Optional[str] = Field(default=None)


class MinistryScheduleCommand(BaseModel):
    """Ministry schedule row."""

    days_of_week: list[int] = Field(default_factory=list)
    start_time: Optional[time] = Field(default=None)
    end_time: Optional[time] = Field(default=None)
    effective_from: Optional[date] = Field(default=None)
    effective_to: Optional[date] = Field(default=None)
    sequence: Optional[float] = Field(default=None)


class PositionTranslationCommand(BaseModel):
    """Localized position display."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class CreateMinistryCommand(BaseModel):
    """Create ministry (no stable code)."""

    name: Optional[str] = Field(default=None)
    owner_position_id: Optional[UUID] = Field(default=None)
    ministry_type_id: Optional[UUID] = Field(default=None)
    target_audience_ids: list[UUID] = Field(default_factory=list)
    schedules: list[MinistryScheduleCommand] = Field(default_factory=list)
    has_priority_booking: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: list[OrgTranslationCommand] = Field(..., min_length=1)


class UpdateMinistryCommand(BaseModel):
    """Update ministry."""

    name: Optional[str] = Field(default=None)
    owner_position_id: Optional[UUID] = Field(default=None)
    ministry_type_id: Optional[UUID] = Field(default=None)
    target_audience_ids: Optional[list[UUID]] = Field(default=None)
    schedules: Optional[list[MinistryScheduleCommand]] = Field(default=None)
    has_priority_booking: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: Optional[list[OrgTranslationCommand]] = Field(default=None)


class MinistryMemberEntryCommand(BaseModel):
    """Ministry member row (primary / secondary)."""

    user_id: UUID = Field(...)
    member_role: MinistryMemberRole = Field(...)
    remark: Optional[str] = Field(default=None)
    contact_email: Optional[str] = Field(default=None)


class ReplaceMinistryMembersCommand(BaseModel):
    """Replace ministry members (primary / secondary stewards)."""

    members: list[MinistryMemberEntryCommand] = Field(default_factory=list)


class SubmitMinistryCommand(BaseModel):
    """Submit ministry for approval."""


class ApproveMinistryCommand(BaseModel):
    """Approve pending ministry."""

    comment: Optional[str] = Field(default=None)


class RejectMinistryCommand(BaseModel):
    """Reject pending ministry."""

    rejection_reason: str = Field(...)
    comment: Optional[str] = Field(default=None)


class MinistryApplicationCommand(BaseModel):
    """Create ministry application with members."""

    owner_position_id: UUID = Field(...)
    has_priority_booking: bool = Field(default=False)
    translations: list[OrgTranslationCommand] = Field(default_factory=list)
    members: list[MinistryMemberEntryCommand] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations:
            return self
        raise ValueError("translations are required")


class CreatePositionCommand(BaseModel):
    """Create leadership position."""

    code: str = Field(...)
    team: PositionTeam = Field(...)
    office: PositionOffice = Field(...)
    can_own_ministry: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: Optional[list[PositionTranslationCommand]] = Field(default=None)

    @model_validator(mode="after")
    def validate_translations(self):
        if self.translations:
            return self
        raise ValueError("translations are required")


class UpdatePositionCommand(BaseModel):
    """Update leadership position (code immutable)."""

    team: PositionTeam = Field(...)
    office: PositionOffice = Field(...)
    can_own_ministry: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    translations: Optional[list[PositionTranslationCommand]] = Field(default=None)


class AssignPositionCommand(BaseModel):
    """Assign incumbent to position."""

    user_id: UUID = Field(...)
    start_at: Optional[datetime] = Field(default=None)


class CreateMemberPersonCommand(BaseModel):
    """Create member person record."""

    legal_name: Optional[str] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)


class UpdateMemberPersonCommand(BaseModel):
    """Update member person record."""

    legal_name: Optional[str] = Field(default=None)


class LinkMemberPersonCommand(BaseModel):
    """Link auth user to member person."""

    user_id: UUID = Field(...)
