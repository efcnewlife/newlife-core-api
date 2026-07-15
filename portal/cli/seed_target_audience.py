"""
Target audience seed CLI commands.
"""
import asyncio

import click

from portal.application.cli.catalog_seed_service import run_catalog_seed
from portal.config import settings
from portal.container import Container
from portal.libs.logger import logger
from portal.models import OrgTargetAudience, OrgTargetAudienceTranslation

from .datas.target_audience_seed_data import target_audience_seed_rows


async def seed_target_audiences() -> None:
    """Seed org target audiences from target_audience_seed_data."""
    container = Container()
    session = container.db_session()
    try:
        await run_catalog_seed(
            session,
            target_audience_seed_rows,
            catalog_model=OrgTargetAudience,
            translation_model=OrgTargetAudienceTranslation,
            catalog_fk_field="target_audience_id",
            label="target audiences",
        )
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Target audience seed failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def seed_target_audiences_process(*, force: bool = False) -> None:
    """Synchronous entry to run target audience seed."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"seed-target-audiences is blocked when ENV={settings.ENV!r}. Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This upserts org target audiences and translations from target_audience_seed_data "
                "(by code). Existing rows with matching codes will be updated.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Seeding org target audiences...", fg="cyan"))
    asyncio.run(seed_target_audiences())
    click.echo(click.style("Done.", fg="green"))
