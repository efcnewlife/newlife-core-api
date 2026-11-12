"""
Util functions for lifespan
"""

from asyncio import CancelledError, Event, create_task
from contextlib import asynccontextmanager, suppress
from os import environ

from fastapi import FastAPI

from portal.application.facility.pending_payment_expiry_job import pending_payment_expiry_loop
from portal.config import settings
from portal.container import Container
from portal.libs.database.aio_redis import create_redis_client
from portal.libs.depends.rate_limiters import attach_rate_limiters, create_redis_rate_limiters
from portal.libs.logger import logger
from portal.libs.telemetry import flush_telemetry


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
            redis_connection = create_redis_client(settings.REDIS_URL)
            attach_rate_limiters(app, await create_redis_rate_limiters(redis_connection))
            logger.info("Redis rate limiters initialized")
        except Exception as e:
            logger.error("Failed to initialize Redis rate limiters: %s", e)
            attach_rate_limiters(app, None)

    sweep_stop = Event()
    sweep_task = None
    if hasattr(app, "container") and not environ.get("PYTEST_CURRENT_TEST"):
        sweep_task = create_task(pending_payment_expiry_loop(app.container, sweep_stop))
        logger.info("Pending-payment expiry sweep started")
    yield

    sweep_stop.set()
    if sweep_task is not None:
        sweep_task.cancel()
        with suppress(CancelledError):
            await sweep_task

    if redis_connection is not None:
        try:
            await redis_connection.aclose()
        except Exception as e:
            logger.warning("Failed to close Redis rate limiter connection: %s", e)

    logger.info("Lifespan finished")
    flush_telemetry()
