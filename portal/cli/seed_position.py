"""
Position seed CLI commands.
"""
import asyncio

import click

from portal.application.cli.position_seed_service import run_position_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.position_seed_data import position_seed_rows


async def seed_positions() -> None:
    """Seed org positions from docs/position.md."""
    container = Container()
    session = container.db_session()
    try:
        await run_position_seed(session, position_seed_rows)
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Position seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_positions_process(*, force: bool = False) -> None:
    """Synchronous entry to run position seed."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"seed-positions is blocked when ENV={settings.ENV!r}. Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This upserts org positions and translations from position_seed_data "
                "(by position code). Existing rows with matching codes will be updated.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding org positions...", fg="cyan"))
    asyncio.run(seed_positions())
    click.echo(click.style("Done.", fg="green"))
