"""
Member person serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins import PaginationBaseResponseModel
from portal.serializers.mixins.model_mixins import UUIDBaseModel


class AdminMemberPersonDetail(UUIDBaseModel):
    """Member person detail."""

    legal_name: Optional[str] = Field(None, serialization_alias="legalName", description="Legal name")
    user_id: Optional[UUID] = Field(None, serialization_alias="userId", description="Linked user ID")
    email: Optional[str] = Field(None, description="Linked user email")
    display_name: Optional[str] = Field(None, serialization_alias="displayName", description="Linked user display name")


class AdminMemberPersonPages(PaginationBaseResponseModel):
    """Paginated member persons."""

    items: list[AdminMemberPersonDetail] = Field(default_factory=list, description="Items")


class AdminMemberPersonCreate(BaseModel):
    """Create member person."""

    legal_name: Optional[str] = Field(None, description="Legal name")
    user_id: Optional[UUID] = Field(None, description="Linked user ID")


class AdminMemberPersonUpdate(BaseModel):
    """Update member person."""

    legal_name: Optional[str] = Field(None, description="Legal name")


class AdminMemberPersonLink(BaseModel):
    """Link user to member person."""

    user_id: UUID = Field(..., description="User ID")
