"""
PostgreSQL connection manager
"""
import asyncio
from enum import Enum
from typing import Optional, Dict, Any

import asyncpg

from portal.config import settings

__all__ = ["PostgresConnection", "PostgresConnection", "ConnectionType"]


class ConnectionType(Enum):
    DEFAULT = "DEFAULT"
    POOL = "POOL"


class PostgresContext:
    def __init__(
        self,
        key: str,
        schema: str = None,
        application_name: str = None,
        **connect_kwargs
    ):
        self.key: str = key
        self.schema: str = schema
        self.application_name: str = application_name
        self.pool: Optional[asyncpg.pool.Pool] = None
        self.connect_kwargs: dict = connect_kwargs


class PostgresConnection:
    """PostgreSQL connection pool manager"""

    def __init__(self):
        self._contexts: Dict[str, PostgresContext] = {}
        self._lock = asyncio.Lock()

    async def create_connection(
        self,
        connection_type: ConnectionType = ConnectionType.DEFAULT,
        command_timeout: int = None,
        loop=None,
    ):
        match connection_type:
            case ConnectionType.POOL:
                return await self._create_pool(command_timeout=command_timeout)
            case ConnectionType.DEFAULT:
                return await self._create_connection(command_timeout=command_timeout, loop=loop)
            case _:
                raise TypeError(
                    f'Failed to create connection, invalid database key "{connection_type}", '
                    f'please register with setup first'
                )

    async def _create_pool(
        self,
        connection_type: ConnectionType = ConnectionType.POOL,
        command_timeout: int = None
    ) -> asyncpg.pool.Pool:
        """Create a connection pool"""
        context = self._get_context(connection_type)
        if not context:
            context = self._setup(
                connection_type,
                dsn=settings.SQLALCHEMY_DATABASE_URI,
                schema=settings.DATABASE_SCHEMA,
                application_name=settings.DATABASE_APPLICATION_NAME,
                min_size=0,
                max_size=100,
                command_timeout=command_timeout
            )

        if context.pool is not None:
            return context.pool

        async with self._lock:
            if context.pool is not None:
                return context.pool

            server_settings = await self._create_server_settings(context)
            if command_timeout:
                context.connect_kwargs['command_timeout'] = command_timeout

            context.pool = await asyncpg.create_pool(
                server_settings=server_settings,
                max_inactive_connection_lifetime=60 * 10,
                **context.connect_kwargs
            )
            return context.pool

    async def _create_connection(
        self,
        connection_type: ConnectionType = ConnectionType.DEFAULT,
        command_timeout: int = None,
        loop=None,
    ) -> asyncpg.Connection:
        """Create a single connection"""
        context = self._get_context(connection_type)
        if not context:
            if connection_type == ConnectionType.DEFAULT:
                context = self._setup(
                    connection_type,
                    dsn=settings.SQLALCHEMY_DATABASE_URI,
                    schema=settings.DATABASE_SCHEMA,
                    application_name=settings.DATABASE_APPLICATION_NAME,
                    command_timeout=command_timeout
                )
            else:
                raise TypeError(
                    f'Failed to create connection, invalid database key "{connection_type}", '
                    f'please register with setup first'
                )

        server_settings = await self._create_server_settings(context)
        if command_timeout:
            context.connect_kwargs['command_timeout'] = command_timeout

        return await asyncpg.connect(
            server_settings=server_settings,
            **context.connect_kwargs,
            loop=loop
        )

    async def _create_server_settings(self, context: PostgresContext) -> Optional[Dict[str, Any]]:
        """Create server settings for connection"""
        if context.application_name:
            return {'application_name': context.application_name}
        return None

    def _setup(self, connection_type: ConnectionType = ConnectionType.DEFAULT, application_name: str = None, **kwargs) -> PostgresContext:
        """Setup a database context"""
        if not kwargs:
            raise TypeError('kwargs is not null')

        key = connection_type.value if isinstance(connection_type, ConnectionType) else str(connection_type)
        if key in self._contexts:
            self._contexts[key].connect_kwargs = kwargs
        else:
            self._contexts[key] = PostgresContext(key, application_name=application_name, **kwargs)

        return self._contexts[key]

    def _get_context(self, connection_type: ConnectionType = ConnectionType.DEFAULT) -> Optional[PostgresContext]:
        """Get a database context by key"""
        real_key = connection_type.value if isinstance(connection_type, ConnectionType) else str(connection_type)
        return self._contexts.get(real_key, None)
