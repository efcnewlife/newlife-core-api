"""
Member-facing org API serializers.
"""
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from portal.serializers.mixins.model_mixins import UUIDBaseModel


class ApiOrgMinistryItem(UUIDBaseModel):
    """Owned ministry list item."""

    name: Optional[str] = Field(None, description="Ministry name")
    status: str = Field(..., description="Lifecycle status")
    has_priority_booking: bool = Field(
        False,
        serialization_alias="hasPriorityBooking",
        description="Priority booking flag",
    )


class ApiOrgMinistryList(BaseModel):
    """Owned ministries."""

    items: list[ApiOrgMinistryItem] = Field(default_factory=list, description="Items")


class ApiAssignablePositionItem(UUIDBaseModel):
    """Assignable position for ministry application."""

    code: str = Field(..., description="Position code")
    team: Optional[str] = Field(None, description="Team label")
    office: Optional[str] = Field(None, description="Office label")
    name: Optional[str] = Field(None, description="Position name")
    incumbent_user_id: Optional[UUID] = Field(
        None,
        serialization_alias="incumbentUserId",
        description="Incumbent user ID",
    )


class ApiAssignablePositionList(BaseModel):
    """Assignable positions."""

    items: list[ApiAssignablePositionItem] = Field(default_factory=list, description="Items")
