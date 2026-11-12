"""
Real-Redis checks for the single database 0 keyspace (EFC-293).

Proves per-client rate limiting over HTTP, recovery after the server loses its script cache, and TTL-backed
auth state against a local, disposable Redis; offline substitutes cannot. This does not prove
Azure Managed Redis compatibility. Opt-in: needs REDIS_URL pointing at a throwaway Redis.

    PORTAL_REDIS_INTEGRATION=1 REDIS_URL=redis://localhost:6391/0 uv run pytest tests/integration/test_redis_db0.py -v
"""

import os
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
import pytest_asyncio
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from portal.config import settings
from portal.libs.database import RedisPool
from portal.libs.database.aio_redis import create_redis_client
from portal.libs.depends.rate_limiters import RedisRateLimiterDependency, create_redis_rate_limiters, get_rate_limiters_config
from portal.providers.member_refresh_app_binding_provider import MemberRefreshAppBindingProvider
from portal.providers.token_blacklist_provider import TokenBlacklistProvider

pytestmark = pytest.mark.skipif(
    os.getenv("PORTAL_REDIS_INTEGRATION") != "1" or not settings.REDIS_URL, reason="set PORTAL_REDIS_INTEGRATION=1 and REDIS_URL to run against a local Redis"
)

RATE_LIMITER_PATTERN = f"{settings.APP_NAME}:rate_limiter:*"


@pytest_asyncio.fixture
async def redis():
    client = create_redis_client(settings.REDIS_URL)
    await _delete_matching(client, RATE_LIMITER_PATTERN)
    yield client
    await _delete_matching(client, RATE_LIMITER_PATTERN)
    await client.aclose()


async def _delete_matching(client, pattern: str) -> None:
    keys = [key async for key in client.scan_iter(match=pattern)]
    if keys:
        await client.delete(*keys)


async def _rate_limited_app(redis) -> FastAPI:
    app = FastAPI()
    app.state.rate_limiters = await create_redis_rate_limiters(redis)

    @app.get("/limited", dependencies=[Depends(RedisRateLimiterDependency("default"))])
    async def limited():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_connection_uses_database_zero(redis):
    assert redis.connection_pool.connection_kwargs.get("db", 0) == 0
    assert await redis.ping() is True


@pytest.mark.asyncio
async def test_each_client_gets_429_beyond_its_own_short_window(redis):
    app = await _rate_limited_app(redis)
    config = get_rate_limiters_config("default")
    first = {"X-Forwarded-For": "203.0.113.1"}
    second = {"X-Forwarded-For": "203.0.113.2"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        statuses = [(await client.get("/limited", headers=first)).status_code for _ in range(config.short.times + 1)]
        other_client = (await client.get("/limited", headers=second)).status_code

    assert statuses[: config.short.times] == [200] * config.short.times
    assert statuses[-1] == 429
    assert other_client == 200

    key = f"{settings.APP_NAME}:rate_limiter:default:203.0.113.1:/limited"
    assert await redis.zcard(key) == config.short.times
    assert 0 < await redis.pttl(key) <= config.long.seconds * 1000


@pytest.mark.asyncio
async def test_rate_limiting_survives_script_flush(redis):
    app = await _rate_limited_app(redis)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = (await client.get("/limited")).status_code
        await redis.script_flush()
        after = (await client.get("/limited")).status_code

    assert (before, after) == (200, 200)


@pytest.mark.asyncio
async def test_auth_state_is_namespaced_and_expires(redis):
    pool = RedisPool()
    blacklist = TokenBlacklistProvider(redis_client=pool)
    binding = MemberRefreshAppBindingProvider(redis_client=pool)
    token = f"integration-{uuid4()}"
    family_id = uuid4()

    assert await blacklist.add_to_blacklist(token, datetime.now(timezone.utc) + timedelta(seconds=60)) is True
    await binding.bind(family_id, "facility-booking")
    try:
        assert await blacklist.is_blacklisted(token) is True
        assert 0 < await redis.ttl(blacklist._get_blacklist_key(token)) <= 60
        assert await binding.get_app_code(family_id) == "facility-booking"
        assert await redis.ttl(binding._key(family_id)) > 0
    finally:
        await redis.delete(blacklist._get_blacklist_key(token))
        await binding.clear(family_id)
        await pool.create().aclose()
