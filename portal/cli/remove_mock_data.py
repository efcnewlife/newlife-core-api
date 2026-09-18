"""
remove-mock-data CLI: hard-delete every @test.local Mock user, its derived QA
business data, and mock:-marked slot templates / Blackouts, while preserving
catalog data and CSV archives (ADR 0025).
"""

import asyncio

import click

from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error
from portal.application.cli.remove_mock_data_service import MockDataDependencyError, RemoveMockDataService
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

COMMAND_NAME = "remove-mock-data"


async def remove_mock_data(*, include_legacy_demo: bool = False) -> None:
    container = Container()
    session = container.db_session()
    try:
        service = RemoveMockDataService(session)
        await service.run(include_legacy_demo=include_legacy_demo)
    except MockDataDependencyError as error:
        await session.rollback()
        click.echo(click.style(f"remove-mock-data failed: {error}", fg="red"))
        raise SystemExit(1) from error
    except Exception as error:
        # Checks run before any delete, but roll back defensively on any later failure too.
        await session.rollback()
        click.echo(click.style(f"remove-mock-data failed: {error}", fg="red"))
        logger.exception(error)
        raise SystemExit(1) from error
    finally:
        await session.close()


def remove_mock_data_process(*, force: bool = False, include_legacy_demo: bool = False) -> None:
    """Synchronous entry: environment guard, confirmation, then the async orchestration."""
    guard_error = mock_lifecycle_environment_guard_error(is_prod=settings.IS_PROD, is_dev=settings.IS_DEV, force=force, command_name=COMMAND_NAME)
    if guard_error:
        click.echo(click.style(guard_error, fg="red"))
        raise SystemExit(1)

    if not force:
        warning = (
            "WARNING: This permanently deletes every @test.local Mock user and its derived data: profiles, "
            "tokens, Bookings, Recurring Booking Series, Booking Drafts, Ministries, steward/position "
            "relationships, and mock:-marked slot templates and Blackouts. Catalog data (locales, RBAC, "
            "positions, rooms, rates, system settings, Legal Documents, Ministry Types) and CSV archives "
            "are preserved. Fails without deleting anything if a candidate Ministry also has a non-Mock-user "
            "dependency."
        )
        if include_legacy_demo:
            warning += (
                " --include-legacy-demo also removes the exact known seed.*@local.test Demo accounts and "
                "seed:-marked fixtures, and fails on a non-legacy dependency."
            )
        click.echo(click.style(warning, fg="yellow"))
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Removing Mock QA data...", fg="cyan"))
    asyncio.run(remove_mock_data(include_legacy_demo=include_legacy_demo))
    click.echo(click.style("Done.", fg="green"))
