"""
Local demo seed CLI: ministries, slot templates/blackouts, and bookings.
"""

import asyncio

import click

from portal.application.cli.facility_booking_seed_service import run_facility_booking_seed
from portal.application.cli.facility_slot_seed_service import run_facility_slot_seed
from portal.application.cli.ministry_seed_service import run_ministry_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

from .datas.facility_booking_seed_data import demo_personal_booker_seed_rows
from .datas.facility_slot_seed_data import facility_blackout_seed_rows
from .datas.ministry_seed_data import demo_ministry_user_seed_rows, ministry_seed_rows


async def seed_local_demo() -> None:
    """Run demo ministry → slots/blackouts → bookings on one session."""
    container = Container()
    session = container.db_session()
    try:
        click.echo(click.style("Seeding demo ministries...", fg="cyan"))
        await run_ministry_seed(session, ministry_seed_rows, demo_user_rows=demo_ministry_user_seed_rows, commit=False)

        click.echo(click.style("Seeding demo slot templates and blackouts...", fg="cyan"))
        await run_facility_slot_seed(session, blackout_rows=facility_blackout_seed_rows, commit=False)

        click.echo(click.style("Seeding demo bookings...", fg="cyan"))
        await run_facility_booking_seed(session, personal_booker_rows=demo_personal_booker_seed_rows, commit=False)

        await session.commit()
        click.echo(click.style("Local demo pack committed.", fg="green"))
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"seed-local-demo failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_local_demo_process(*, force: bool = False) -> None:
    """Synchronous entry for the local demo seed pack."""
    if not settings.IS_DEV and not force:
        click.echo(click.style(f"seed-local-demo is blocked when ENV={settings.ENV!r}. Pass --force to proceed.", fg="red"))
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This replaces demo-prefixed ministries (seed: Demo ), "
                "slot templates/blackouts (seed:), and bookings (seed: remark). "
                "Admin-created rows without those prefixes are left untouched. "
                "Catalog must already exist (locales, ministry types, audiences, "
                "positions, facility rental rooms). Suggested flow: catalog seeds "
                "→ create-superuser (optional) → seed-local-demo.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding local demo pack...", fg="cyan"))
    asyncio.run(seed_local_demo())
    click.echo(click.style("Done.", fg="green"))
