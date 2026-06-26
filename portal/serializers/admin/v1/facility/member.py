"""
Admin facility member serializers.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.base import GenericQueryBaseModel, PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminMemberQuery(GenericQueryBaseModel):
    """Member list filters."""

    ministry_id: Optional[UUID] = Field(default=None)


class AdminMemberMinistryTag(UUIDBaseModel):
    """Ministry tag."""

    code: str = Field(...)
    name: Optional[str] = Field(default=None)


class AdminMemberListItem(UUIDBaseModel):
    """Member list row."""

    email: Optional[str] = Field(default=None)
    display_name: Optional[str] = Field(default=None, serialization_alias="displayName")
    last_login_at: Optional[datetime] = Field(default=None, serialization_alias="lastLoginAt")
    ministries: list[AdminMemberMinistryTag] = Field(default_factory=list)


class AdminMemberPages(PaginationBaseResponseModel):
    """Paginated members."""

    items: list[AdminMemberListItem] = Field(default_factory=list)


class AdminMemberDetail(AdminMemberListItem):
    """Member detail."""

    pass


class AdminMemberMinistriesUpdate(BaseModel):
    """Replace ministry memberships."""

    ministry_ids: list[UUID] = Field(default_factory=list)
