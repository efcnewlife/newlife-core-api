"""
AioRedis
"""

from redis.asyncio import Redis, from_url
from redis.asyncio.retry import Retry
from redis.backoff import ExponentialWithJitterBackoff
from redis.exceptions import ConnectionError, TimeoutError

from portal.config import settings

HEALTH_CHECK_INTERVAL_SECONDS = 30


def create_redis_client(url: str) -> Redis:
    """
    Create a Redis client for the single database 0 keyspace.
    The database and TLS come from the URL (rediss:// verifies the server certificate and hostname).
    Retries ride out failover and restarts; health checks catch idle connections closed by the server.
    """
    return from_url(
        url=url,
        encoding="utf-8",
        decode_responses=True,
        retry=Retry(ExponentialWithJitterBackoff(base=0.5, cap=5), retries=3),
        retry_on_error=[ConnectionError, TimeoutError],
        health_check_interval=HEALTH_CHECK_INTERVAL_SECONDS,
        socket_keepalive=True,
    )


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
