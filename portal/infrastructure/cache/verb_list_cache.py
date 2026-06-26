"""
Redis cache for admin verb list.
"""
from uuid import UUID

from redis.asyncio import Redis

from portal.application.rbac.results import VerbListResult
from portal.config import settings
from portal.domain.rbac.entities import VerbListItem
from portal.libs.consts.cache_keys import CacheKeys, CacheExpiry
from portal.libs.database import RedisPool


class VerbListCache:
    """Cache verb lists keyed by locale id."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    def _cache_key(self, locale_id: UUID) -> str:
        return (
            CacheKeys(resource="verb")
            .add_attribute("list")
            .add_attribute(str(locale_id))
            .build()
        )

    async def get(self, locale_id: UUID) -> list[VerbListItem] | None:
        """
        Return cached verb list or None on miss.
        :param locale_id:
        :return:
        """
        cached = await self._redis.get(self._cache_key(locale_id))
        if not cached:
            return None
        result = VerbListResult.model_validate_json(cached)
        return result.items

    async def set(self, locale_id: UUID, items: list[VerbListItem]) -> None:
        """
        Store verb list in cache.
        :param locale_id:
        :param items:
        :return:
        """
        await self._redis.set(
            self._cache_key(locale_id),
            VerbListResult(items=items).model_dump_json(),
            ex=CacheExpiry.MONTH,
        )
