"""
Core infrastructure container: config, database, redis, security providers.
"""

from dependency_injector import containers, providers

from portal.config import settings
from portal.libs.database import PostgresConnection, RedisPool, Session
from portal.libs.database.session_proxy import SessionProxy
from portal.providers.jwt_provider import JWTProvider
from portal.providers.microsoft_graph_provider import MicrosoftGraphProvider
from portal.providers.microsoft_oidc_provider import MicrosoftOidcProvider
from portal.providers.password_provider import PasswordProvider
from portal.providers.refresh_token_provider import RefreshTokenProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider


class CoreContainer(containers.DeclarativeContainer):
    """Database, cache, and cross-cutting providers."""

    config = providers.Configuration()
    config.from_pydantic(settings)

    postgres_connection = providers.Singleton(PostgresConnection)
    db_session = providers.Factory(Session, postgres_connection=postgres_connection)
    request_session = providers.Factory(SessionProxy)

    redis_client = providers.Singleton(RedisPool)

    token_blacklist_provider = providers.Factory(
        TokenBlacklistProvider,
        redis_client=redis_client,
    )
    jwt_provider = providers.Singleton(
        JWTProvider,
        token_blacklist_provider=token_blacklist_provider,
    )
    password_provider = providers.Singleton(PasswordProvider)
    refresh_token_provider = providers.Factory(
        RefreshTokenProvider,
        session=request_session,
    )
    microsoft_oidc_provider = providers.Singleton(MicrosoftOidcProvider)
    microsoft_graph_provider = providers.Singleton(MicrosoftGraphProvider)
