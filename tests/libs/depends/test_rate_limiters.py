"""
Redis-backed rate limiters: one sliding-window key per client identifier in the database 0 keyspace,
reaching mounted sub-apps.
"""

import pytest
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient

from portal.libs.depends.rate_limiters import RedisRateLimiterDependency, attach_rate_limiters, create_redis_rate_limiters, get_rate_limiters_config


class _FakeScript:
    def __init__(self, result: int):
        self.result = result
        self.calls: list[tuple[list[str], list]] = []

    async def __call__(self, keys=None, args=None):
        self.calls.append((list(keys), list(args)))
        return self.result


class _FakeRedis:
    """Records the registered sliding-window script; the script itself runs only against real Redis."""

    def __init__(self, result: int = 1):
        self.script = _FakeScript(result)

    def register_script(self, script: str) -> _FakeScript:
        return self.script


@pytest.mark.asyncio
async def test_each_config_type_has_one_limiter_covering_all_windows():
    redis = _FakeRedis()
    limiters = await create_redis_rate_limiters(redis)

    assert set(limiters) == {"default", "read", "write"}
    assert all(len(config_limiters) == 1 for config_limiters in limiters.values())

    assert await limiters["default"][0].try_acquire_async("10.0.0.1:/admin/api/v1/auth/me") is True

    config = get_rate_limiters_config("default")
    keys, args = redis.script.calls[0]
    assert keys == ["newlife-core-api:rate_limiter:default:10.0.0.1:/admin/api/v1/auth/me"]
    assert args[2:] == [
        config.short.seconds * 1000,
        config.short.times,
        config.medium.seconds * 1000,
        config.medium.times,
        config.long.seconds * 1000,
        config.long.times,
    ]


@pytest.mark.asyncio
async def test_each_client_identifier_gets_its_own_key():
    redis = _FakeRedis()
    limiter = (await create_redis_rate_limiters(redis))["read"][0]

    await limiter.try_acquire_async("10.0.0.1:/admin/api/v1/auth/me")
    await limiter.try_acquire_async("10.0.0.2:/admin/api/v1/auth/me")
    await limiter.try_acquire_async("10.0.0.1:/admin/api/v1/user/me")

    keys = [call[0][0] for call in redis.script.calls]
    assert len(set(keys)) == 3
    assert all(key.startswith("newlife-core-api:rate_limiter:read:") for key in keys)


@pytest.mark.asyncio
async def test_each_request_is_recorded_as_a_distinct_member():
    redis = _FakeRedis()
    limiter = (await create_redis_rate_limiters(redis))["default"][0]

    await limiter.try_acquire_async("ip:/path")
    await limiter.try_acquire_async("ip:/path")

    members = [call[1][1] for call in redis.script.calls]
    assert members[0] != members[1]


@pytest.mark.asyncio
async def test_script_rejection_is_reported():
    limiter = (await create_redis_rate_limiters(_FakeRedis(result=0)))["write"][0]

    assert await limiter.try_acquire_async("ip:/path") is False


class _RejectingLimiter:
    async def try_acquire_async(self, name: str, blocking: bool = False) -> bool:
        return False


def _main_with_mounted_admin() -> FastAPI:
    admin = FastAPI()

    @admin.get("/limited", dependencies=[Depends(RedisRateLimiterDependency("default"))])
    async def limited():
        return {"ok": True}

    main = FastAPI()
    main.mount("/admin", admin)
    return main


@pytest.mark.asyncio
async def test_limiters_attached_at_startup_apply_to_mounted_sub_apps():
    main = _main_with_mounted_admin()
    attach_rate_limiters(main, {"default": [_RejectingLimiter()]})

    async with AsyncClient(transport=ASGITransport(app=main), base_url="http://test") as client:
        response = await client.get("/admin/limited")

    assert response.status_code == 429


@pytest.mark.asyncio
async def test_no_limiters_attached_lets_requests_through():
    main = _main_with_mounted_admin()
    attach_rate_limiters(main, None)

    async with AsyncClient(transport=ASGITransport(app=main), base_url="http://test") as client:
        response = await client.get("/admin/limited")

    assert response.status_code == 200
