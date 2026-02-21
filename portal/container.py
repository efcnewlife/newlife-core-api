"""
Container - Template: Core providers and handlers only
"""

from dependency_injector import containers, providers

from portal import handlers
from portal.config import settings
from portal.libs.authorization.permission_checker import PermissionChecker
from portal.libs.database import RedisPool, PostgresConnection, Session
from portal.libs.database.session_proxy import SessionProxy
from portal.libs.events.bus import EventBus
from portal.libs.logger import logger
from portal.providers.jwt_provider import JWTProvider
from portal.providers.password_provider import PasswordProvider
from portal.providers.refresh_token_provider import RefreshTokenProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider


class Container(containers.DeclarativeContainer):
    """Container - Template with core services only"""

    wiring_config = containers.WiringConfiguration(
        modules=[],
        packages=[
            "portal.authorization",
            "portal.handlers",
            "portal.routers",
            "portal.middlewares",
        ],
    )

    # [App Base]
    config = providers.Configuration()
    config.from_pydantic(settings)

    # [Database]
    postgres_connection = providers.Singleton(PostgresConnection)
    db_session = providers.Factory(Session, postgres_connection=postgres_connection)
    request_session = providers.Factory(SessionProxy)

    # [Redis]
    redis_client = providers.Singleton(RedisPool)

    # [Providers]
    token_blacklist_provider = providers.Factory(
        TokenBlacklistProvider, redis_client=redis_client
    )
    jwt_provider = providers.Singleton(
        JWTProvider, token_blacklist_provider=token_blacklist_provider
    )
    password_provider = providers.Singleton(PasswordProvider)
    refresh_token_provider = providers.Factory(
        RefreshTokenProvider,
        session=request_session,
    )

    # [Handlers - minimal for auth]
    user_handler = providers.Factory(
        handlers.UserHandler, session=request_session, redis_client=redis_client
    )
    admin_user_handler = providers.Factory(
        handlers.AdminUserHandler,
        session=request_session,
        redis_client=redis_client,
        password_provider=password_provider,
    )

    # [Authorization]
    permission_checker = providers.Factory(
        PermissionChecker,
        redis_client=redis_client,
    )

    # [Event Bus]
    event_bus = providers.Singleton(EventBus)

    @staticmethod
    def register_event_handlers(event_bus_instance: EventBus, container: "Container") -> None:
        """
        Register all event handlers to the event bus
        :param event_bus_instance:
        :param container: Container instance to use for creating handlers
        :return:
        """
        logger.debug("No event handlers registered")
