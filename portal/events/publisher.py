"""
Event publisher helper
"""

from typing import Optional

from portal.libs.logger import logger
from .base import BaseEvent
from .bus import EventBus


def get_event_bus() -> Optional[EventBus]:
    """
    Get event bus from the process runtime container.
    :return:
    """
    try:
        from portal.runtime_context import get_runtime_container

        container = get_runtime_container()
        if container is None:
            logger.warning("Runtime container not set, event bus unavailable")
            return None
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
