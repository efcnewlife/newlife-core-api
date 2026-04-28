"""
Locale initialization CLI commands.
"""
import asyncio

import click

from portal.container import Container
from portal.libs.logger import logger
from portal.models import SystemLocale

from .datas.locale_data import seed_locales


async def init_locales() -> None:
    """
    Seed locales into SystemLocale table.
    """
    container = Container()
    session = container.db_session()
    try:
        for locale in seed_locales:
            await (
                session
                .insert(SystemLocale)
                .values(**locale)
                .on_conflict_do_update(
                    index_elements=["language_code", "script_code", "region_code"],
                    set_=dict(
                        name=locale.get("name"),
                        native_name=locale.get("native_name"),
                        is_active=locale.get("is_active", True),
                        is_default=locale.get("is_default", False),
                    ),
                )
                .execute()
            )
        await session.commit()
        click.echo(click.style("Locales initialized successfully.", fg="bright_green"))
        logger.info(f"Locale init completed. locales upserted: {len(seed_locales)}")
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"Locale init failed: {e}", fg="red"))
        logger.exception(e)
        raise
    finally:
        await session.close()


def init_locales_process() -> None:
    """Synchronous entry to run locale initialization."""
    click.echo(click.style("Initializing locales...", fg="cyan"))
    asyncio.run(init_locales())
    click.echo(click.style("Done.", fg="green"))
