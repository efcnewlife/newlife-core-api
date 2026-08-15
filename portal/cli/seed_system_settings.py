"""
System setting seed CLI.
"""

import asyncio

import click

from portal.application.cli.system_setting_seed_service import SystemSettingSeedService
from portal.cli.datas.system_setting_seed_data import seed_system_settings
from portal.container import Container
from portal.libs.logger import logger


async def seed_system_settings_async() -> None:
    """Seed public.system_setting rows (insert-if-missing)."""
    container = Container()
    session = container.db_session()
    try:
        service = SystemSettingSeedService(session)
        await service.run(seed_system_settings)
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"System setting seed failed: {e}", fg="red"))
        logger.exception(e)
        raise
    finally:
        await session.close()


def seed_system_settings_process() -> None:
    """Synchronous entry for system setting seed."""
    asyncio.run(seed_system_settings_async())
