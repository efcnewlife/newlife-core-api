"""
Token Blacklist Provider for managing revoked tokens
"""
import hashlib
from datetime import datetime, timezone

from redis.asyncio import Redis

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.database import RedisPool


class TokenBlacklistProvider:
    """Token Blacklist Provider for managing revoked tokens"""

    def __init__(self, redis_client: RedisPool):
        self.redis: Redis = redis_client.create(db=settings.REDIS_DB)

    def _get_token_hash(self, token: str) -> str:
        """Generate hash for token to use as Redis key"""
        return hashlib.sha256(token.encode()).hexdigest()

    def _get_blacklist_key(self, token: str) -> str:
        """Get Redis key for blacklist token"""
        token_hash = self._get_token_hash(token)
        return CacheKeys("token_blacklist").add_attribute(token_hash).build()

    def _get_refresh_blacklist_key(self, token: str) -> str:
        """Get Redis key for blacklisted refresh token"""
        token_hash = self._get_token_hash(token)
        return CacheKeys("refresh_token_blacklist").add_attribute(token_hash).build()

    async def add_to_blacklist(self, token: str, expires_at: datetime) -> bool:
        """
        Add token to blacklist with expiration
        """
        try:
            key = self._get_blacklist_key(token)
            # Calculate TTL in seconds
            ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())

            if ttl > 0:
                await self.redis.setex(key, ttl, "1")
                return True
            return False
        except Exception:
            return False

    async def is_blacklisted(self, token: str) -> bool:
        """
        Check if token is blacklisted
        """
        try:
            key = self._get_blacklist_key(token)
            exists = await self.redis.exists(key)
            return bool(exists)
        except Exception:
            return False
