"""
Locale initialization CLI commands.
"""
import asyncio

import click

from portal.application.cli.locale_seed_service import LocaleSeedService
from portal.container import Container
from portal.libs.logger import logger

from .datas.locale_data import seed_locales


async def init_locales() -> None:
    """
    Seed locales into SystemLocale table.
    """
    container = Container()
    session = container.db_session()
    try:
        service = LocaleSeedService(session)
        await service.run(seed_locales)
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"Locale init failed: {e}", fg="red"))
        logger.exception(e)
        raise
    finally:
        await session.close()


def init_locales_process() -> None:
    """Synchronous entry to run locale initialization."""
    asyncio.run(init_locales())
