"""
Event Bus for event-driven architecture
"""
from typing import Dict, List, Type

from portal.libs.events.base import BaseEvent, EventHandler
from portal.libs.logger import logger


class EventBus:
    """
    Event bus for publishing and subscribing to events
    """

    def __init__(self):
        """
        Initialize event bus
        """
        self._handlers: Dict[Type[BaseEvent], List[EventHandler]] = {}

    def subscribe(self, event_type: Type[BaseEvent], handler: EventHandler) -> None:
        """
        Subscribe a handler to an event type
        :param event_type:
        :param handler:
        :return:
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.info(f"Subscribed handler {handler.__class__.__name__} to event {event_type.__name__}")

    def unsubscribe(self, event_type: Type[BaseEvent], handler: EventHandler) -> None:
        """
        Unsubscribe a handler from an event type
        :param event_type:
        :param handler:
        :return:
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                logger.info(f"Unsubscribed handler {handler.__class__.__name__} from event {event_type.__name__}")
            except ValueError:
                logger.warning(f"Handler {handler.__class__.__name__} not found for event {event_type.__name__}")

    async def publish(self, event: BaseEvent) -> None:
        """
        Publish an event to all subscribed handlers (synchronous execution)
        :param event:
        :return:
        """
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])

        if not handlers:
            logger.debug(f"No handlers registered for event type {event_type.__name__}")
            return

        logger.info(f"Publishing event {event_type.__name__} to {len(handlers)} handler(s)")

        # Execute all handlers concurrently
        import asyncio
        tasks = [self._execute_handler(handler, event) for handler in handlers]
        await asyncio.gather(*tasks, return_exceptions=True)

    def publish_in_background(self, event: BaseEvent) -> None:
        """
        Publish an event in background (fire-and-forget)
        :param event:
        :return:
        """
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_running_loop()
            # Create task and don't await it (fire-and-forget)
            loop.create_task(self.publish(event))
            logger.debug(
                "Event %s scheduled for background execution", event.event_type
            )
        except RuntimeError:
            # If no event loop is running, this is a programming error
            # In async context, there should always be a running loop
            logger.error(
                "No running event loop found for background event %s. "
                "This should not happen in async context. "
                "Event will not be processed.",
                event.event_type,
            )

    async def _execute_handler(self, handler: EventHandler, event: BaseEvent) -> None:
        """
        Execute a handler with error handling
        :param handler:
        :param event:
        :return:
        """
        try:
            await handler.handle(event)
            logger.debug(f"Handler {handler.__class__.__name__} successfully processed event {event.event_type}")
        except Exception as e:
            logger.error(
                f"Error in handler {handler.__class__.__name__} for event {event.event_type}: {str(e)}",
                exc_info=True
            )
            # Re-raise to allow caller to handle if needed
            raise

    def get_handlers_count(self, event_type: Type[BaseEvent]) -> int:
        """
        Get the number of handlers for an event type
        :param event_type:
        :return:
        """
        return len(self._handlers.get(event_type, []))

    def clear(self) -> None:
        """
        Clear all handlers
        :return:
        """
        self._handlers.clear()
        logger.info("Event bus cleared")

