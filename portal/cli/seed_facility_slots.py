"""
Facility slot template and blackout seed CLI commands.
"""

import asyncio

import click

from portal.application.cli.facility_slot_seed_service import run_facility_slot_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.facility_slot_seed_data import facility_blackout_seed_rows, facility_slot_template_seed_rows


async def seed_facility_slots() -> None:
    """Seed demo room slot templates and blackouts for existing rooms."""
    container = Container()
    session = container.db_session()
    try:
        await run_facility_slot_seed(session, slot_rows=facility_slot_template_seed_rows, blackout_rows=facility_blackout_seed_rows)
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Facility slot seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_facility_slots_process(*, force: bool = False) -> None:
    """Synchronous entry to run facility slot / blackout seed."""
    if not settings.IS_DEV and not force:
        click.echo(click.style(f"seed-facility-slots is blocked when ENV={settings.ENV!r}. Pass --force to proceed.", fg="red"))
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This replaces demo slot templates and blackouts whose names start "
                "with 'seed:' (hard delete + re-insert). Admin-created rows without that "
                "prefix are left untouched. Rooms must already exist (e.g. after "
                "seed-facility-rental).",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding facility slot templates and blackouts...", fg="cyan"))
    asyncio.run(seed_facility_slots())
    click.echo(click.style("Done.", fg="green"))
