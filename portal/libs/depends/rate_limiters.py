"""
Rate limiters dependencies for API endpoints.

Rate limiters strategy:
1. Short-term rate limiting (1 second): Prevent sudden traffic, protect system stability
2. Medium-term rate limiting (30 seconds): Smooth traffic, avoid too many requests in a short period of time
3. Long-term rate limiting (1 hour): Total control, prevent long-term abuse

Different endpoint types rate limiters strategy:
- Read endpoint: Looser, because read operations are less burdened on the system
- Write endpoint: Stricter, because write operations need more resources

When REDIS_URL is set, limiters use RedisBucket for distributed rate limiting across workers.
Otherwise in-memory limiters are used (per-process).

Configuration file location: env/rate_limiters.yaml
"""
from fastapi import Depends, Request
from fastapi.exceptions import HTTPException
from fastapi_limiter.depends import RateLimiter
from pyrate_limiter import Duration, Limiter, Rate
from pyrate_limiter.buckets.redis_bucket import RedisBucket

from portal.config import settings
from portal.schemas.rate_limiter import RateLimiterConfig


async def default_identifier(request: Request) -> str:
    """
    Identifier for rate limit key, same as fastapi-limiter: IP + path.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    elif request.client:
        ip = request.client.host
    else:
        ip = "127.0.0.1"
    return f"{ip}:{request.scope['path']}"


def create_rate_limiters(config: RateLimiterConfig) -> list:
    """
    Create rate limiters list from RateLimiterConfig Model

    :param config: Rate limiter config Model
    :return: Rate limiters list
    """
    return [
        Depends(
            RateLimiter(
                limiter=Limiter(Rate(config.short.times, Duration.SECOND * config.short.seconds))
            )
        ),
        Depends(
            RateLimiter(
                limiter=Limiter(Rate(config.medium.times, Duration.SECOND * config.medium.seconds))
            )
        ),
        Depends(
            RateLimiter(
                limiter=Limiter(Rate(config.long.times, Duration.SECOND * config.long.seconds))
            )
        ),
    ]


def get_rate_limiters_config(config_type: str = "default") -> RateLimiterConfig:
    """
    Get rate limiter config from configuration file

    :param config_type: Configuration type (default, read, write, admin)
    :return:
    """
    if not settings.RATE_LIMITERS_CONFIG:
        # If configuration is not loaded, return default value
        from portal.schemas.rate_limiter import RateLimitWindow
        return RateLimiterConfig(
            short=RateLimitWindow(times=3, seconds=1),
            medium=RateLimitWindow(times=20, seconds=30),
            long=RateLimitWindow(times=400, seconds=3600),
        )

    # Get configuration by configuration type
    config_map = {
        "default": settings.RATE_LIMITERS_CONFIG.default,
        "read": settings.RATE_LIMITERS_CONFIG.read,
        "write": settings.RATE_LIMITERS_CONFIG.write,
    }

    return config_map.get(config_type, settings.RATE_LIMITERS_CONFIG.default)


async def create_redis_rate_limiters(redis) -> dict[str, list[Limiter]]:
    """
    Create Redis-backed limiters for default, read, and write config types.
    Each config type has three limiters (short, medium, long). Caller must pass
    an async Redis connection (e.g. from redis.asyncio.from_url).

    :param redis: Async Redis client (redis.asyncio.Redis)
    :return: Dict mapping config_type to list of three Limiters (short, medium, long)
    """
    prefix = f"{settings.APP_NAME}_limiter"
    result: dict[str, list[Limiter]] = {}

    for config_type in ("default", "read", "write"):
        config = get_rate_limiters_config(config_type)
        short_bucket = await RedisBucket.init(  # noqa
            [Rate(config.short.times, Duration.SECOND * config.short.seconds)],
            redis,
            f"{prefix}_{config_type}_short",
        )
        medium_bucket = await RedisBucket.init(  # noqa
            [Rate(config.medium.times, Duration.SECOND * config.medium.seconds)],
            redis,
            f"{prefix}_{config_type}_medium",
        )
        long_bucket = await RedisBucket.init(  # noqa
            [Rate(config.long.times, Duration.SECOND * config.long.seconds)],
            redis,
            f"{prefix}_{config_type}_long",
        )
        result[config_type] = [
            Limiter(short_bucket),
            Limiter(medium_bucket),
            Limiter(long_bucket),
        ]

    return result


class RedisRateLimiterDependency:
    """
    FastAPI dependency that applies Redis-backed rate limiters for a config type.
    Requires app.state.rate_limiters to be set (done in lifespan when REDIS_URL is set).
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


def _get_rate_limiters_dependencies() -> tuple[list, list, list]:
    """
    Return (DEFAULT_RATE_LIMITERS, READ_RATE_LIMITERS, WRITE_RATE_LIMITERS).
    Uses Redis-backed dependency when REDIS_URL is set, otherwise in-memory limiters.
    """
    if settings.REDIS_URL:
        return (
            [Depends(RedisRateLimiterDependency("default"))],
            [Depends(RedisRateLimiterDependency("read"))],
            [Depends(RedisRateLimiterDependency("write"))],
        )
    return (
        create_rate_limiters(get_rate_limiters_config("default")),
        create_rate_limiters(get_rate_limiters_config("read")),
        create_rate_limiters(get_rate_limiters_config("write")),
    )


_default, _read, _write = _get_rate_limiters_dependencies()

# Default rate limiter (for general endpoints)
DEFAULT_RATE_LIMITERS = _default
# Read endpoint rate limiter (looser)
READ_RATE_LIMITERS = _read
# Write endpoint rate limiter (stricter)
WRITE_RATE_LIMITERS = _write
