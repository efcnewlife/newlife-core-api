"""
AioRedis
"""
from redis.asyncio import Redis, from_url

from portal.config import settings


class RedisPool:
    """RedisPool"""

    def __init__(self):
        self._uri = settings.REDIS_URL
        self._redis = None

    def create(self, db: int = 0) -> Redis:
        """

        :return:
        """
        if self._redis:
            return self._redis
        session = from_url(
            url=self._uri,
            db=db,
            encoding="utf-8",
            decode_responses=True
        )
        self._redis = session
        return session
