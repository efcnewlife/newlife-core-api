"""
Event definitions - Template: Core user events only
"""

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import Field

from portal.libs.events.base import BaseEvent


class UserCreatedEvent(BaseEvent):
    """Event emitted when a user is created"""
    user_id: UUID
    email: str
    name: Optional[str] = None
    additional_data: Dict[str, Any] = Field(default_factory=dict)


class UserUpdatedEvent(BaseEvent):
    """Event emitted when a user is updated"""
    user_id: UUID
    updated_fields: Dict[str, Any]
    previous_data: Optional[Dict[str, Any]] = None


class UserLoggedInEvent(BaseEvent):
    """Event emitted when a user logs in"""
    user_id: UUID
    login_method: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
