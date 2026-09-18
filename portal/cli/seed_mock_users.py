"""
seed-mock-users CLI: complete Mock Testing-account and Ministry inventory, archived to SharePoint (ADR 0025).
"""

import asyncio
from pathlib import Path

import click

from portal.application.cli.mock_account_archive import MockSeedArchiveCollisionError
from portal.application.cli.mock_lifecycle_guard import mock_lifecycle_environment_guard_error
from portal.application.cli.seed_mock_users_service import (
    MockSeedArchiveUploadError,
    MockSeedCatalogPrerequisiteError,
    MockSnapshotExistsError,
    SeedMockUsersService,
)
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger

COMMAND_NAME = "seed-mock-users"


async def seed_mock_users() -> None:
    container = Container()
    session = container.db_session()
    archive_writer = container.sharepoint_archive_provider()
    try:
        service = SeedMockUsersService(
            session, archive_writer, env=settings.ENV, default_locale_code=settings.DEFAULT_LOCALE, output_dir=Path(settings.MOCK_SEED_OUTPUT_DIR)
        )
        await service.run()
    except MockSnapshotExistsError as error:
        await session.rollback()
        click.echo(click.style(f"seed-mock-users failed: {error}", fg="red"))
        raise SystemExit(1) from error
    except MockSeedCatalogPrerequisiteError as error:
        await session.rollback()
        click.echo(click.style(f"seed-mock-users failed: {error}", fg="red"))
        raise SystemExit(1) from error
    except MockSeedArchiveCollisionError as error:
        click.echo(
            click.style(
                f"seed-mock-users failed: {error} Data was committed as an active Mock snapshot. Run remove-mock-data, then retry after the next minute.",
                fg="red",
            )
        )
        raise SystemExit(1) from error
    except MockSeedArchiveUploadError as error:
        click.echo(
            click.style(
                f"seed-mock-users: database seed committed but the SharePoint archive upload failed. Local CSV pair retained at {error.account_csv} "
                f"and {error.ministry_csv}. See application logs for the upload error.",
                fg="red",
            )
        )
        logger.exception(error)
        raise SystemExit(1) from error
    except Exception as error:
        # Reached before the single seed commit (e.g. the Ministry Type NOT-NULL schema
        # error); rolling back here discards the whole batch, including the personas
        # already inserted earlier in this same uncommitted transaction.
        await session.rollback()
        click.echo(click.style(f"seed-mock-users failed: {error}", fg="red"))
        logger.exception(error)
        raise SystemExit(1) from error
    finally:
        await session.close()


def seed_mock_users_process(*, force: bool = False) -> None:
    """Synchronous entry: environment guard, confirmation, then the async orchestration."""
    guard_error = mock_lifecycle_environment_guard_error(is_prod=settings.IS_PROD, is_dev=settings.IS_DEV, force=force, command_name=COMMAND_NAME)
    if guard_error:
        click.echo(click.style(guard_error, fg="red"))
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This creates the complete Mock inventory: five personal, three steward, one owner, and "
                "one inactive @test.local Testing accounts plus ten scheduled Mock Ministries, then archives the "
                "account/Ministry CSV pair locally and to SharePoint. Catalog data (locales) must already exist. "
                "A new run is rejected while an active Mock snapshot exists; run remove-mock-data first.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding Mock users...", fg="cyan"))
    asyncio.run(seed_mock_users())
    click.echo(click.style("Done.", fg="green"))
