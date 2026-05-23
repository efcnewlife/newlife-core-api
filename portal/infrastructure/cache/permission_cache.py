"""
Redis cache for user permissions and admin permission list.
"""
from uuid import UUID

from redis.asyncio import Redis

from portal.config import settings
from portal.domain.rbac.entities import PermissionRecord
from portal.libs.consts.cache_keys import CacheKeys, CacheExpiry
from portal.libs.database import RedisPool


class PermissionCache:
    """User permission hash and admin list cache."""

    def __init__(self, redis_client: RedisPool):
        self._redis: Redis = redis_client.create(db=settings.REDIS_DB)

    @staticmethod
    def permission_key(user_id: UUID, permission_code: str | None = None) -> str:
        """
        Generate Redis key for user permissions.
        :param user_id:
        :param permission_code:
        :return:
        """
        if permission_code:
            return (
                CacheKeys(resource="permission")
                .add_attribute(str(user_id))
                .add_attribute(permission_code)
                .build()
            )
        return CacheKeys(resource="permission").add_attribute(str(user_id)).build()

    def _list_cache_key(self, locale_id: UUID) -> str:
        return (
            CacheKeys(resource="permission")
            .add_attribute("list")
            .add_attribute(str(locale_id))
            .build()
        )

    async def clear_user_permissions_cache(self, user_id: UUID) -> None:
        """
        Clear cached permissions for a user.
        :param user_id:
        :return:
        """
        key = self.permission_key(user_id=user_id)
        await self._redis.delete(key)

    async def init_user_permissions_cache(
        self,
        user_id: UUID,
        permissions: list[PermissionRecord],
        expire: int,
    ) -> list[str]:
        """
        Store user permissions in Redis hash.
        :param user_id:
        :param permissions:
        :param expire:
        :return:
        """
        await self.clear_user_permissions_cache(user_id=user_id)
        if not permissions:
            return []
        key = self.permission_key(user_id=user_id)
        permission_codes: list[str] = []
        for permission in permissions:
            permission_code = permission.code
            permission_codes.append(permission_code)
            await self._redis.hset(key, permission_code, permission.model_dump_json())
        await self._redis.expire(key, expire)
        return permission_codes

    async def get_permission_list_json(self, locale_id: UUID) -> str | None:
        """
        Return cached admin permission list JSON or None on miss.
        :param locale_id:
        :return:
        """
        return await self._redis.get(self._list_cache_key(locale_id))

    async def set_permission_list_json(self, locale_id: UUID, payload_json: str) -> None:
        """
        Cache admin permission list JSON.
        :param locale_id:
        :param payload_json:
        :return:
        """
        await self._redis.set(
            self._list_cache_key(locale_id),
            payload_json,
            ex=CacheExpiry.MONTH,
        )
