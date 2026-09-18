"""
seed-mock-data CLI: complete the near-term Facility Booking fixture suite for the
current local Mock inventory (ADR 0025).
"""

import asyncio
from pathlib import Path

import click

from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error
from portal.application.cli.seed_mock_data_service import MockDataPrerequisiteError, SeedMockDataService
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

COMMAND_NAME = "seed-mock-data"


async def seed_mock_data() -> None:
    container = Container()
    session = container.db_session()
    try:
        service = SeedMockDataService(session, env=settings.ENV, default_locale_code=settings.DEFAULT_LOCALE, output_dir=Path(settings.MOCK_SEED_OUTPUT_DIR))
        await service.run()
    except MockDataPrerequisiteError as error:
        await session.rollback()
        click.echo(click.style(f"seed-mock-data failed: {error}", fg="red"))
        raise SystemExit(1) from error
    except Exception as error:
        # All writes happen in one uncommitted transaction; rolling back here discards
        # the whole batch, including anything already inserted earlier in this run.
        await session.rollback()
        click.echo(click.style(f"seed-mock-data failed: {error}", fg="red"))
        logger.exception(error)
        raise SystemExit(1) from error
    finally:
        await session.close()


def seed_mock_data_process(*, force: bool = False) -> None:
    """Synchronous entry: environment guard, confirmation, then the async orchestration."""
    guard_error = mock_lifecycle_environment_guard_error(is_prod=settings.IS_PROD, is_dev=settings.IS_DEV, force=force, command_name=COMMAND_NAME)
    if guard_error:
        click.echo(click.style(guard_error, fg="red"))
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This reads the current local Mock inventory (seed-mock-users) and creates weekly slot templates, "
                "campus-wide and room-specific Blackouts, ten confirmed Bookings, an Owner-position assignment, "
                "and a pending Ministry Application. It does not create Testing accounts or inventory Ministries.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding Mock Facility Booking fixtures...", fg="cyan"))
    asyncio.run(seed_mock_data())
    click.echo(click.style("Done.", fg="green"))
