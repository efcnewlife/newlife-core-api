"""
Event base classes
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


class BaseEvent(BaseModel, ABC):
    """
    Base class for all events
    """
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def set_event_type(self) -> "BaseEvent":
        """
        Set event_type based on class name
        """
        if not self.event_type:
            self.event_type = self.__class__.__name__
        return self


class EventHandler(ABC):
    """
    Base class for event handlers
    """

    @property
    @abstractmethod
    def event_type(self) -> type[BaseEvent]:
        """
        Return the event type this handler handles
        :return:
        """

    @abstractmethod
    async def handle(self, event: BaseEvent) -> None:
        """
        Handle the event
        :param event:
        :return:
        """
