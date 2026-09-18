"""
seed-mock-data CLI: complete the Facility Booking QA scenarios for the current local
Mock user inventory (ADR 0025).
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
                "WARNING: This reads the current local Mock user inventory (seed-mock-users) and creates a personal "
                "Rental Booking, activates the steward Ministry with a Church Activity Booking, assigns the owner "
                "Mock user to an Owner position, and creates a pending Ministry Application in that Owner's queue.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding Mock Booking and approval scenarios...", fg="cyan"))
    asyncio.run(seed_mock_data())
    click.echo(click.style("Done.", fg="green"))
