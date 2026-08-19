"""
Demo ministry seed CLI commands.
"""

import asyncio

import click

from portal.application.cli.ministry_seed_service import run_ministry_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.ministry_seed_data import demo_ministry_user_seed_rows, ministry_seed_rows


async def seed_ministries() -> None:
    """Seed demo Active ministries with a simulated approval."""
    container = Container()
    session = container.db_session()
    try:
        await run_ministry_seed(session, ministry_seed_rows, demo_user_rows=demo_ministry_user_seed_rows)
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Ministry seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_ministries_process(*, force: bool = False) -> None:
    """Synchronous entry to run the demo ministry seed."""
    if not settings.IS_DEV and not force:
        click.echo(click.style(f"seed-ministries is blocked when ENV={settings.ENV!r}. Pass --force to proceed.", fg="red"))
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This replaces demo ministries whose localized names start with "
                "'seed: Demo ' (hard delete + re-insert). Admin-created ministries without "
                "that prefix are left untouched. Locales, ministry types, target audiences, "
                "and positions that can own a ministry must already exist (init-locales, "
                "seed-ministry-types, seed-target-audiences, seed-positions).",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding demo ministries...", fg="cyan"))
    asyncio.run(seed_ministries())
    click.echo(click.style("Done.", fg="green"))
