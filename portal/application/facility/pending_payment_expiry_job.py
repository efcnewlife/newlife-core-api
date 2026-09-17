"""
FastAPI lifecycle runner for Pending-payment hold expiry.
"""

import asyncio
from typing import Any

from portal.domain.facility.constants import PENDING_PAYMENT_SWEEP_INTERVAL_SECONDS
from portal.libs.contexts.request_session_context import reset_request_session, set_request_session
from portal.libs.logger import logger


async def run_pending_payment_expiry_once(container: Any) -> None:
    """Run one idempotent expiry sweep using a dedicated database session."""
    session = container.db_session()
    token = set_request_session(session)
    service = None
    try:
        service = container.recurring_booking_service()
        await service.expire_pending_holds()
        await session.commit()
    except Exception:
        await session.rollback()
        logger.exception("Pending-payment hold expiry sweep failed")
    finally:
        if service is not None:
            try:
                await service.release_pending_payment_sweep_lock()
            except Exception:
                logger.exception("Failed to release pending-payment sweep lock")
        reset_request_session(token)
        await session.close()


async def pending_payment_expiry_loop(container: Any, stop_event: asyncio.Event) -> None:
    """Startup catch-up, then sweep every 15 minutes until stop_event is set."""
    await run_pending_payment_expiry_once(container)
    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=PENDING_PAYMENT_SWEEP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            await run_pending_payment_expiry_once(container)
