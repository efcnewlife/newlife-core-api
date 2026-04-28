"""
Util functions for lifespan
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from redis.asyncio import from_url as redis_from_url

from portal.config import settings
from portal.container import Container
from portal.libs.depends.rate_limiters import create_redis_rate_limiters
from portal.libs.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan
    :param app:
    """
    logger.info("Starting lifespan")
    # Register event handlers (optional - add Container.register_event_handlers in your project)
    if hasattr(app, "container"):
        try:
            container = app.container
            event_bus = container.event_bus()
            logger.info("-" * 100)
            Container.register_event_handlers(event_bus, container)
            logger.info("Event handlers registered")
            logger.info("-" * 100)
        except Exception as e:
            logger.warning("Failed to register event handlers: %s", e)

    redis_connection = None
    if settings.REDIS_URL:
        try:
            redis_connection = redis_from_url(
                settings.REDIS_URL,
                db=settings.RATE_LIMITER_REDIS_DB,
                encoding="utf-8",
                decode_responses=True,
            )
            app.state.rate_limiters = await create_redis_rate_limiters(redis_connection)
            logger.info("Redis rate limiters initialized")
        except Exception as e:
            logger.error("Failed to initialize Redis rate limiters: %s", e)
            app.state.rate_limiters = None
    yield

    if redis_connection is not None:
        try:
            await redis_connection.aclose()
        except Exception as e:
            logger.warning("Failed to close Redis rate limiter connection: %s", e)

    logger.info("Lifespan finished")
