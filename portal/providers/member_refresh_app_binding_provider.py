"""
Bind refresh-token families to member web app codes (Redis; avoids DB migration).
"""
from uuid import UUID

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.database import RedisPool


class MemberRefreshAppBindingProvider:
    """Store family_id -> app_code for member refresh tokens."""

    def __init__(self, redis_client: RedisPool):
        self.redis: Redis = redis_client.create(db=settings.REDIS_DB)
        self._ttl_seconds = max(1, settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60)

    def _key(self, family_id: UUID) -> str:
        return CacheKeys("member_refresh_app").add_attribute(str(family_id)).build()

    async def bind(self, family_id: UUID, app_code: str) -> None:
        await self.redis.setex(self._key(family_id), self._ttl_seconds, app_code)

    async def get_app_code(self, family_id: UUID) -> str | None:
        value = await self.redis.get(self._key(family_id))
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    async def clear(self, family_id: UUID) -> None:
        await self.redis.delete(self._key(family_id))
