"""
Event-Driven Architecture Module - Template
"""

from portal.libs.events.base import BaseEvent, EventHandler
from portal.libs.events.bus import EventBus
from portal.libs.events.definitions import (
    UserCreatedEvent,
    UserUpdatedEvent,
    UserLoggedInEvent,
)
from portal.libs.events.publisher import publish_event, publish_event_in_background

__all__ = [
    "BaseEvent",
    "EventHandler",
    "EventBus",
    "UserCreatedEvent",
    "UserUpdatedEvent",
    "UserLoggedInEvent",
    "publish_event",
    "publish_event_in_background",
]
