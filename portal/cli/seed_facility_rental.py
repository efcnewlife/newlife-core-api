"""
Facility rental catalog seed CLI commands.
"""

import asyncio

import click

from portal.application.cli.facility_rental_seed_service import run_facility_rental_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.facility_rental_seed_data import (
    GLOBAL_RATE_UNIT_AMOUNT,
    facility_discount_seed_rows,
    facility_policy_seed_rows,
    facility_rental_rate_template_seed_rows,
    facility_room_seed_rows,
    facility_surcharge_seed_rows,
)


async def seed_facility_rental(*, reset: bool = False) -> None:
    """Seed facility rooms, templates, rates, and rental catalog from rental policy PDF data."""
    container = Container()
    session = container.db_session()
    try:
        await run_facility_rental_seed(
            session,
            room_rows=facility_room_seed_rows,
            template_rows=facility_rental_rate_template_seed_rows,
            discount_rows=facility_discount_seed_rows,
            surcharge_rows=facility_surcharge_seed_rows,
            policy_rows=facility_policy_seed_rows,
            global_rate_unit_amount=GLOBAL_RATE_UNIT_AMOUNT,
            reset=reset,
        )
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Facility rental seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_facility_rental_process(*, force: bool = False, reset: bool = False) -> None:
    """Synchronous entry to run facility rental seed."""
    if not settings.IS_DEV and not force:
        click.echo(click.style(f"seed-facility-rental is blocked when ENV={settings.ENV!r}. Pass --force to proceed.", fg="red"))
        raise SystemExit(1)

    if not force:
        if reset:
            click.echo(
                click.style(
                    "WARNING: --reset hard-deletes facility bookings, slot templates, rooms, "
                    "rental rate templates, rental rates, discounts, surcharges, and policy "
                    "settings, then re-seeds from facility_rental_seed_data. This cannot be undone.",
                    fg="yellow",
                )
            )
        else:
            click.echo(
                click.style(
                    "WARNING: This upserts facility rooms, rental rate templates, rental rates, "
                    "discounts, surcharges, and policy settings from facility_rental_seed_data. "
                    "Existing matching rows will be updated.",
                    fg="yellow",
                )
            )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    action = "Resetting and seeding" if reset else "Seeding"
    click.echo(click.style(f"{action} facility rental catalog...", fg="cyan"))
    asyncio.run(seed_facility_rental(reset=reset))
    click.echo(click.style("Done.", fg="green"))
