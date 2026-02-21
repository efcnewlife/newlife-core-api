"""
Event publisher helper
"""

from typing import Optional

from portal.libs.events.base import BaseEvent
from portal.libs.events.bus import EventBus
from portal.libs.logger import logger

# Global container instance (set during app initialization)
_global_container: Optional[object] = None


def set_global_container(container) -> None:
    """
    Set the global container instance
    :param container:
    :return:
    """
    global _global_container
    _global_container = container


def get_event_bus() -> Optional[EventBus]:
    """
    Get event bus from container
    :return:
    """
    try:
        if _global_container is None:
            # Import here to avoid circular import
            from portal.container import Container

            # Fallback: create new instance if global not set
            # This should not happen in normal operation
            logger.warning("Global container not set, creating new instance")
            container = Container()
        else:
            container = _global_container
        return container.event_bus()
    except Exception as e:
        logger.error("Failed to get event bus: %s", e)
        return None


async def publish_event(event: BaseEvent) -> None:
    """
    Publish an event to the event bus (synchronous execution)
    :param event:
    :return:
    """
    event_bus = get_event_bus()
    if event_bus:
        await event_bus.publish(event)
    else:
        logger.warning(
            "Event bus not available, event %s not published", event.event_type
        )


def publish_event_in_background(event: BaseEvent) -> None:
    """
    Publish an event in background (fire-and-forget)
    :param event:
    :return:
    """
    event_bus = get_event_bus()
    if event_bus:
        event_bus.publish_in_background(event)
    else:
        logger.warning(
            "Event bus not available, event %s not published", event.event_type
        )
