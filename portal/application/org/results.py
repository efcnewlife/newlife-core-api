"""
Organization application results.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.domain.common.mixins import JsonStringParseModel, UUIDBaseModel

__all__ = [
    "AssignablePositionResult",
    "CreateIdResult",
    "MemberPersonDetailResult",
    "MemberPersonPageResult",
    "MinistryApprovalResult",
    "MinistryDetailResult",
    "MinistryListItemResult",
    "MinistryListResult",
    "MinistryMemberResult",
    "MinistryPageResult",
    "PositionDetailResult",
    "PositionListItemResult",
    "PositionPageResult",
    "PositionTranslationItemResult",
    "TranslationItemResult",
]


class CreateIdResult(UUIDBaseModel):
    """Created entity id."""


class TranslationItemResult(JsonStringParseModel):
    """Ministry translation row."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class PositionTranslationItemResult(JsonStringParseModel):
    """Position translation row."""

    locale_id: UUID = Field(...)
    name: str = Field(...)
    description: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class MinistryMemberResult(BaseModel):
    """Ministry member (primary / secondary steward)."""

    user_id: UUID = Field(...)
    member_role: str = Field(...)
    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)
    remark: Optional[str] = Field(default=None)


class MinistryListItemResult(UUIDBaseModel):
    """Ministry list row."""

    name: Optional[str] = Field(default=None)
    status: str = Field(...)
    has_priority_booking: bool = Field(default=False)
    is_active: bool = Field(default=True)


class MinistryDetailResult(UUIDBaseModel):
    """Ministry detail."""

    name: Optional[str] = Field(default=None)
    status: str = Field(...)
    owner_position_id: Optional[UUID] = Field(default=None)
    has_priority_booking: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    submitted_at: Optional[datetime] = Field(default=None)
    submitted_by_id: Optional[UUID] = Field(default=None)
    approved_at: Optional[datetime] = Field(default=None)
    approved_by_id: Optional[UUID] = Field(default=None)
    rejected_at: Optional[datetime] = Field(default=None)
    rejected_by_id: Optional[UUID] = Field(default=None)
    rejection_reason: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    translations: list[TranslationItemResult] = Field(default_factory=list)
    members: list[MinistryMemberResult] = Field(default_factory=list)


class MinistryPageResult(BaseModel):
    """Paginated ministries."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[MinistryDetailResult] = Field(default_factory=list)


class MinistryListResult(BaseModel):
    """Active ministries dropdown."""

    items: list[MinistryListItemResult] = Field(default_factory=list)


class MinistryApprovalResult(UUIDBaseModel):
    """Ministry approval request row."""

    ministry_id: UUID = Field(...)
    ministry_name: Optional[str] = Field(default=None)
    owner_position_id: Optional[UUID] = Field(default=None)
    status: str = Field(...)
    requested_by_id: Optional[UUID] = Field(default=None)
    resolved_by_id: Optional[UUID] = Field(default=None)
    decided_at: Optional[datetime] = Field(default=None)
    comment: Optional[str] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)


class PositionListItemResult(UUIDBaseModel):
    """Position list row."""

    code: str = Field(...)
    team: Optional[str] = Field(default=None)
    office: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    can_own_ministry: bool = Field(default=False)
    is_active: bool = Field(default=True)


class PositionDetailResult(UUIDBaseModel):
    """Position detail."""

    code: str = Field(...)
    team: Optional[str] = Field(default=None)
    office: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    can_own_ministry: bool = Field(default=False)
    is_active: bool = Field(default=True)
    sequence: Optional[float] = Field(default=None)
    created_at: Optional[datetime] = Field(default=None)
    created_by: Optional[str] = Field(default=None)
    updated_at: Optional[datetime] = Field(default=None)
    updated_by: Optional[str] = Field(default=None)
    delete_reason: Optional[str] = Field(default=None)
    translations: list[PositionTranslationItemResult] = Field(default_factory=list)
    current_user_id: Optional[UUID] = Field(default=None)


class PositionPageResult(BaseModel):
    """Paginated positions."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[PositionDetailResult] = Field(default_factory=list)


class AssignablePositionResult(UUIDBaseModel):
    """Position available for ministry ownership."""

    code: str = Field(...)
    team: Optional[str] = Field(default=None)
    office: Optional[str] = Field(default=None)
    name: Optional[str] = Field(default=None)
    incumbent_user_id: Optional[UUID] = Field(default=None)
    incumbent_display_name: Optional[str] = Field(default=None)


class MemberPersonDetailResult(UUIDBaseModel):
    """Member person detail."""

    legal_name: Optional[str] = Field(default=None)
    user_id: Optional[UUID] = Field(default=None)
    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None)


class MemberPersonPageResult(BaseModel):
    """Paginated member persons."""

    page: int = Field(...)
    page_size: int = Field(...)
    total: int = Field(...)
    items: list[MemberPersonDetailResult] = Field(default_factory=list)
