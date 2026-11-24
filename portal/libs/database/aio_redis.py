"""
AioRedis
"""

import asyncio

from redis.asyncio import BlockingConnectionPool, Redis
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError, MaxConnectionsError, TimeoutError

from portal.config import settings

HEALTH_CHECK_INTERVAL_SECONDS = 30
POOL_MAX_CONNECTIONS = 100
POOL_TIMEOUT_SECONDS = 5


class WaitingConnectionPool(BlockingConnectionPool):
    """
    Waits for a free connection, then raises MaxConnectionsError. The base class raises a plain ConnectionError,
    which cannot be told apart from an unreachable server.
    """

    async def get_connection(self, command_name=None, *keys, **options):
        try:
            return await super().get_connection()
        except ConnectionError as e:
            if isinstance(e.__cause__, asyncio.TimeoutError):
                raise MaxConnectionsError("Timed out waiting for a Redis connection") from e
            raise


def create_redis_client(url: str) -> Redis:
    """
    Create a Redis client for the single database 0 keyspace.
    The database and TLS come from the URL (rediss:// verifies the server certificate and hostname).
    A busy pool makes commands wait for a free connection instead of failing at once.
    Retries ride out failover and restarts; health checks catch idle connections closed by the server.
    """
    pool = WaitingConnectionPool.from_url(
        url=url,
        max_connections=POOL_MAX_CONNECTIONS,
        timeout=POOL_TIMEOUT_SECONDS,
        encoding="utf-8",
        decode_responses=True,
        retry=Retry(ExponentialWithJitterBackoff(base=0.5, cap=5), retries=3),
        retry_on_error=[ConnectionError, TimeoutError],
        health_check_interval=HEALTH_CHECK_INTERVAL_SECONDS,
        socket_keepalive=True,
    )
    return Redis.from_pool(pool)


class RedisPool:
    """RedisPool"""

    def __init__(self):
        self._uri = settings.REDIS_URL
        self._redis = None

    def create(self) -> Redis:
        """

        :return:
        """
        if self._redis:
            return self._redis
        self._redis = create_redis_client(self._uri)
        return self._redis
