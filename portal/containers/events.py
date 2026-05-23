"""
Event bus and handler registration.
"""

from dependency_injector import containers, providers

from portal.events.bus import EventBus
from portal.events.types import AdminOperationLogEvent
from portal.infrastructure.events.admin_operation_log_handler import AdminOperationLogEventHandler
from portal.libs.logger import logger


class EventsContainer(containers.DeclarativeContainer):
    """Event bus wiring."""

    core = providers.DependenciesContainer()

    event_bus = providers.Singleton(EventBus)

    admin_operation_log_event_handler = providers.Factory(
        AdminOperationLogEventHandler,
        session=core.request_session,
    )

    @staticmethod
    def register_event_handlers(event_bus_instance: EventBus, container: "EventsContainer") -> None:
        """
        Register all event handlers on the event bus.
        :param event_bus_instance:
        :param container:
        :return:
        """
        handler = container.admin_operation_log_event_handler()
        event_bus_instance.subscribe(AdminOperationLogEvent, handler)
        logger.info(
            "Registered %s for %s",
            handler.__class__.__name__,
            AdminOperationLogEvent.__name__,
        )
