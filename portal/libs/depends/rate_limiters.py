"""
Rate limiters dependencies for API endpoints.

Rate limiters strategy:
1. Short-term rate limiting (1 second): Prevent sudden traffic, protect system stability
2. Medium-term rate limiting (30 seconds): Smooth traffic, avoid too many requests in a short period of time
3. Long-term rate limiting (1 hour): Total control, prevent long-term abuse

Different endpoint types rate limiters strategy:
- Read endpoint: Looser, because read operations are less burdened on the system
- Write endpoint: Stricter, because write operations need more resources

Limiters keep one sliding-window sorted set per client identifier (IP + path) in Redis, shared across workers:
`<app>:rate_limiter:<type>:<identifier>` in the database 0 keyspace, expiring after the longest window.
There is no in-process fallback: lifespan attaches the limiters at startup when REDIS_URL is set, and requests are
not limited without them.

Configuration file location: env/rate_limiters.yaml
"""

from time import time_ns
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import HTTPException
from redis.asyncio import Redis
from starlette.routing import Mount

from portal.config import settings
from portal.libs.consts.cache_keys import CacheKeys
from portal.libs.rate_limit.config import RateLimiterConfig

# KEYS[1]: client key. ARGV: now_ms, member, then (interval_ms, limit) per window.
# Rejects without recording when any window is full; otherwise records the request, trims entries
# older than the longest window, and expires the key after it.
SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local longest = 0
for i = 3, #ARGV, 2 do
    local interval = tonumber(ARGV[i])
    if redis.call('ZCOUNT', key, now - interval, now) >= tonumber(ARGV[i + 1]) then
        return 0
    end
    if interval > longest then
        longest = interval
    end
end
redis.call('ZADD', key, now, ARGV[2])
redis.call('ZREMRANGEBYSCORE', key, 0, now - longest)
redis.call('PEXPIRE', key, longest)
return 1
"""


class RedisSlidingWindowLimiter:
    """
    Per-client limiter for one config type, checking all windows in one atomic script call.
    redis-py reloads the script on NOSCRIPT (the script cache is lost on restart or failover).
    """

    def __init__(self, redis: Redis, config_type: str, config: RateLimiterConfig):
        self._script = redis.register_script(SLIDING_WINDOW_SCRIPT)
        self._key_prefix = CacheKeys("rate_limiter").add_attribute(config_type).build()
        self._windows = [value for window in (config.short, config.medium, config.long) for value in (window.seconds * 1000, window.times)]

    async def try_acquire_async(self, name: str, blocking: bool = False) -> bool:
        now_ms = time_ns() // 1_000_000
        allowed = await self._script(keys=[f"{self._key_prefix}:{name}"], args=[now_ms, f"{now_ms}:{uuid4().hex}", *self._windows])
        return bool(allowed)


async def default_identifier(request: Request) -> str:
    """
    Identifier for rate limit key: IP + path.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = "127.0.0.1"
    return f"{ip}:{request.scope['path']}"


def get_rate_limiters_config(config_type: str = "default") -> RateLimiterConfig:
    """
    Get rate limiter config from configuration file

    :param config_type: Configuration type (default, read, write, admin)
    :return:
    """
    if not settings.RATE_LIMITERS_CONFIG:
        # If configuration is not loaded, return default value
        from portal.libs.rate_limit.config import RateLimitWindow

        return RateLimiterConfig(
            short=RateLimitWindow(times=3, seconds=1), medium=RateLimitWindow(times=20, seconds=30), long=RateLimitWindow(times=400, seconds=3600)
        )

    # Get configuration by configuration type
    config_map = {"default": settings.RATE_LIMITERS_CONFIG.default, "read": settings.RATE_LIMITERS_CONFIG.read, "write": settings.RATE_LIMITERS_CONFIG.write}

    return config_map.get(config_type, settings.RATE_LIMITERS_CONFIG.default)


async def create_redis_rate_limiters(redis: Redis) -> dict[str, list[RedisSlidingWindowLimiter]]:
    """
    Create Redis-backed limiters for default, read, and write config types.

    :param redis: Async Redis client (redis.asyncio.Redis)
    :return: Dict mapping config_type to its limiters
    """
    return {config_type: [RedisSlidingWindowLimiter(redis, config_type, get_rate_limiters_config(config_type))] for config_type in ("default", "read", "write")}


def attach_rate_limiters(app: FastAPI, limiters: dict[str, list[RedisSlidingWindowLimiter]] | None) -> None:
    """
    Set Redis-backed limiters on the app and every mounted sub-app.
    Inside a mounted app, request.app is the sub-app, so the root app's state alone is not visible there.
    """
    app.state.rate_limiters = limiters
    for route in app.routes:
        if isinstance(route, Mount) and isinstance(route.app, FastAPI):
            attach_rate_limiters(route.app, limiters)


class RedisRateLimiterDependency:
    """
    FastAPI dependency that applies Redis-backed rate limiters for a config type.
    Requires app.state.rate_limiters to be set (attach_rate_limiters in lifespan).
    """

    def __init__(self, config_type: str):
        self.config_type = config_type

    async def __call__(self, request: Request) -> None:
        limiters = getattr(request.app.state, "rate_limiters", None)
        if not limiters or self.config_type not in limiters:
            return
        identifier = await default_identifier(request)
        for limiter in limiters[self.config_type]:
            acquired = await limiter.try_acquire_async(identifier, blocking=False)
            if not acquired:
                raise HTTPException(status_code=429, detail="Too Many Requests")


# Default rate limiter (for general endpoints)
DEFAULT_RATE_LIMITERS = [Depends(RedisRateLimiterDependency("default"))]
# Read endpoint rate limiter (looser)
READ_RATE_LIMITERS = [Depends(RedisRateLimiterDependency("read"))]
# Write endpoint rate limiter (stricter)
WRITE_RATE_LIMITERS = [Depends(RedisRateLimiterDependency("write"))]
