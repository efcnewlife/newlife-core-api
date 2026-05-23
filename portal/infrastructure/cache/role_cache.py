"""
Redis cache for user roles.
"""
from uuid import UUID

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.database import RedisPool


class RoleCache:
    """User role set cache."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    @staticmethod
    def user_role_key(user_id: UUID) -> str:
        """
        Get user role cache key.
        :param user_id:
        :return:
        """
        return CacheKeys("role").add_attribute(str(user_id)).build()

    async def clear_user_roles_cache(self, user_id: UUID) -> None:
        """
        Clear user roles cache.
        :param user_id:
        :return:
        """
        key = self.user_role_key(user_id)
        await self._redis.delete(key)

    async def init_user_roles_cache(
        self,
        user_id: UUID,
        role_codes: list[str],
        expire: int,
    ) -> list[str]:
        """
        Initialize user roles cache.
        :param user_id:
        :param role_codes:
        :param expire:
        :return:
        """
        await self.clear_user_roles_cache(user_id=user_id)
        if not role_codes:
            return []
        key = self.user_role_key(user_id)
        await self._redis.sadd(key, *role_codes)
        await self._redis.expire(key, expire)
        return role_codes
