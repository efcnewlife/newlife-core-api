"""
Redis cache for system setting values.
"""

import json
from typing import Any, Optional

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheExpiry, CacheKeys
from portal.libs.database import RedisPool


class SettingCache:
    """Per-key JSON value cache for system settings."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    @staticmethod
    def _cache_key(namespace: str, setting_key: str) -> str:
        return CacheKeys(resource="setting").add_attribute(namespace).add_attribute(setting_key).build()

    async def get_value(self, namespace: str, setting_key: str) -> Optional[Any]:
        raw = await self._redis.get(self._cache_key(namespace, setting_key))
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set_value(self, namespace: str, setting_key: str, value: Any) -> None:
        await self._redis.set(self._cache_key(namespace, setting_key), json.dumps(value), ex=CacheExpiry.DAY)

    async def invalidate(self, namespace: str, setting_key: str) -> None:
        await self._redis.delete(self._cache_key(namespace, setting_key))
