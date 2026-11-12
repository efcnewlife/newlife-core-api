"""
Auth state kept in the database 0 keyspace: namespaced keys and TTL expiry (offline Redis substitute).
"""

import hashlib
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from portal.config import settings
from portal.providers.member_refresh_app_binding_provider import MemberRefreshAppBindingProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider


class _ExpiringRedis:
    """In-memory Redis substitute with SETEX/TTL semantics on a manual clock."""

    def __init__(self):
        self.now = 0.0
        self._values: dict[str, tuple[str, float]] = {}

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def _live(self, key: str) -> str | None:
        entry = self._values.get(key)
        if entry is None or entry[1] <= self.now:
            self._values.pop(key, None)
            return None
        return entry[0]

    def ttl(self, key: str) -> int:
        return int(self._values[key][1] - self.now) if self._live(key) is not None else -2

    def keys(self) -> list[str]:
        return [key for key in list(self._values) if self._live(key) is not None]

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self._values[key] = (value, self.now + ttl)

    async def exists(self, key: str) -> int:
        return int(self._live(key) is not None)

    async def get(self, key: str) -> str | None:
        return self._live(key)

    async def delete(self, key: str) -> int:
        return int(self._values.pop(key, None) is not None)


class _Pool:
    def __init__(self, redis: _ExpiringRedis):
        self._redis = redis

    def create(self) -> _ExpiringRedis:
        return self._redis


@pytest.mark.asyncio
async def test_revoked_access_token_is_blacklisted_until_it_would_have_expired():
    redis = _ExpiringRedis()
    provider = TokenBlacklistProvider(redis_client=_Pool(redis))
    token = "header.payload.signature"

    assert await provider.add_to_blacklist(token, datetime.now(timezone.utc) + timedelta(minutes=15)) is True

    key = f"newlife-core-api:token_blacklist:{hashlib.sha256(token.encode()).hexdigest()}"
    assert redis.keys() == [key]
    assert 890 <= redis.ttl(key) <= 900
    assert await provider.is_blacklisted(token) is True

    redis.advance(901)
    assert await provider.is_blacklisted(token) is False


@pytest.mark.asyncio
async def test_already_expired_token_is_not_stored():
    redis = _ExpiringRedis()
    provider = TokenBlacklistProvider(redis_client=_Pool(redis))

    assert await provider.add_to_blacklist("t", datetime.now(timezone.utc) - timedelta(seconds=1)) is False
    assert redis.keys() == []


@pytest.mark.asyncio
async def test_member_refresh_binding_expires_with_the_refresh_token_lifetime():
    redis = _ExpiringRedis()
    provider = MemberRefreshAppBindingProvider(redis_client=_Pool(redis))
    family_id = uuid4()
    lifetime = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    await provider.bind(family_id, "facility-booking")

    key = f"newlife-core-api:member_refresh_app:{family_id}"
    assert redis.keys() == [key]
    assert redis.ttl(key) == lifetime
    assert await provider.get_app_code(family_id) == "facility-booking"

    redis.advance(lifetime)
    assert await provider.get_app_code(family_id) is None


@pytest.mark.asyncio
async def test_member_refresh_binding_clear_removes_the_key():
    redis = _ExpiringRedis()
    provider = MemberRefreshAppBindingProvider(redis_client=_Pool(redis))
    family_id = uuid4()

    await provider.bind(family_id, "facility-booking")
    await provider.clear(family_id)

    assert await provider.get_app_code(family_id) is None
