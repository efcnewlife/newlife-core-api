"""
Redis cache for file signed URLs and association invalidation.
"""
from uuid import UUID

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.database import RedisPool


class FileCache:
    """File signed URL and association cache."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    @staticmethod
    def signed_url_key(file_id: UUID) -> str:
        return (
            CacheKeys(resource="file")
            .add_attribute("signed_url")
            .add_attribute(str(file_id))
            .build()
        )

    @staticmethod
    def resource_association_key(resource_id: UUID) -> str:
        return (
            CacheKeys(resource="file")
            .add_attribute("resource_association")
            .add_attribute(str(resource_id))
            .build()
        )

    async def get_signed_url(self, file_id: UUID) -> str | None:
        value = await self._redis.get(self.signed_url_key(file_id))
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return value

    async def set_signed_url(self, file_id: UUID, url: str, expiry_seconds: int) -> None:
        await self._redis.set(self.signed_url_key(file_id), url, ex=expiry_seconds)

    async def invalidate_signed_url(self, file_id: UUID) -> None:
        await self._redis.delete(self.signed_url_key(file_id))

    async def invalidate_resource_association(self, resource_id: UUID) -> None:
        await self._redis.delete(self.resource_association_key(resource_id))
