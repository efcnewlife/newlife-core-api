"""
Ministry type seed CLI commands.
"""
import asyncio

import click

from portal.application.cli.catalog_seed_service import run_catalog_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger
from portal.models import OrgMinistryType, OrgMinistryTypeTranslation

from .datas.ministry_type_seed_data import ministry_type_seed_rows


async def seed_ministry_types() -> None:
    """Seed org ministry types from ministry_type_seed_data."""
    container = Container()
    session = container.db_session()
    try:
        await run_catalog_seed(
            session,
            ministry_type_seed_rows,
            catalog_model=OrgMinistryType,
            translation_model=OrgMinistryTypeTranslation,
            catalog_fk_field="ministry_type_id",
            label="ministry types",
        )
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Ministry type seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_ministry_types_process(*, force: bool = False) -> None:
    """Synchronous entry to run ministry type seed."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"seed-ministry-types is blocked when ENV={settings.ENV!r}. Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This upserts org ministry types and translations from ministry_type_seed_data "
                "(by code). Existing rows with matching codes will be updated.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding org ministry types...", fg="cyan"))
    asyncio.run(seed_ministry_types())
    click.echo(click.style("Done.", fg="green"))
