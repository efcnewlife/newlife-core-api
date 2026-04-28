"""
Feedback serializers (Admin)
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from portal.libs.consts.enums import FeedbackStatus
from portal.schemas.mixins import UUIDBaseModel
from portal.serializers.mixins import GenericQueryBaseModel, PaginationBaseResponseModel


class AdminFeedbackQuery(GenericQueryBaseModel):
    """
    Feedback query model
    """
    status: Optional[int] = Field(default=None, description="Feedback status (int value)")


class AdminFeedbackBase(UUIDBaseModel):
    """
    Feedback base model
    """
    name: str = Field(..., description="Name")
    email: Optional[str] = Field(default=None, description="Email")
    status: int = Field(default=FeedbackStatus.PENDING.value, description="Status")
    remark: Optional[str] = Field(default=None, description="Remark")
    created_at: Optional[datetime] = Field(default=None, serialization_alias="createdAt", description="Created at")
    updated_at: Optional[datetime] = Field(default=None, serialization_alias="updatedAt", description="Updated at")


class AdminFeedbackItem(AdminFeedbackBase):
    """Feedback item"""
    message: Optional[str] = Field(None, description="Message")


class AdminFeedbackDetail(AdminFeedbackItem):
    """Feedback detail"""
    description: Optional[str] = Field(default=None, description="Description")


class AdminFeedbackPages(PaginationBaseResponseModel):
    items: Optional[list[AdminFeedbackItem]] = Field(..., description="Items")


class AdminFeedbackUpdate(BaseModel):
    """Update feedback status"""
    remark: Optional[str] = Field(default=None, description="Remark")
    description: Optional[str] = Field(default=None, description="Description")
    status: FeedbackStatus = Field(..., description="Status (int value)")
