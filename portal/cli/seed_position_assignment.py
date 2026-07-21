"""
Position assignment seed CLI commands.
"""
import asyncio

import click

from portal.application.cli.position_assignment_seed_service import run_position_assignment_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.position_assignment_seed_data import position_assignment_seed_rows


async def seed_position_assignments() -> None:
    """Seed org position incumbents from roster emails."""
    container = Container()
    session = container.db_session()
    try:
        await run_position_assignment_seed(session, position_assignment_seed_rows)
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Position assignment seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_position_assignments_process(*, force: bool = False) -> None:
    """Synchronous entry to run position assignment seed."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"seed-position-assignments is blocked when ENV={settings.ENV!r}. "
                "Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This assigns incumbents from position_assignment_seed_data "
                "(by user email and position code). Existing open assignments for those "
                "positions will be closed and replaced.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding org position assignments...", fg="cyan"))
    asyncio.run(seed_position_assignments())
    click.echo(click.style("Done.", fg="green"))
