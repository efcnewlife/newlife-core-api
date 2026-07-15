"""
Microsoft Graph user sync CLI command.
"""
import asyncio
from typing import Optional

import click

from portal.application.cli.microsoft_user_sync_service import run_microsoft_user_sync
from portal.config import settings
from portal.container import Container
from portal.infrastructure.persistence.repositories.user_repository import UserRepository
from portal.libs.logger import logger


async def sync_microsoft_users(
    *,
    dry_run: bool,
    filter_expr: Optional[str],
) -> None:
    container = Container()
    session = container.db_session()
    graph_provider = container.microsoft_graph_provider()
    user_repository = UserRepository(session)
    try:
        await run_microsoft_user_sync(
            session,
            user_repository,
            graph_provider,
            dry_run=dry_run,
            filter_expr=filter_expr,
        )
    except Exception as error:
        await session.rollback()
        click.echo(click.style(f"Microsoft user sync failed: {error}", fg="red"))
        logger.exception(error)
        raise
    finally:
        await session.close()


def sync_microsoft_users_process(
    *,
    dry_run: bool = False,
    force: bool = False,
    filter_expr: Optional[str] = None,
) -> None:
    """Synchronous entry to run Microsoft Graph user sync."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"sync-microsoft-users is blocked when ENV={settings.ENV!r}. Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        mode = "dry-run" if dry_run else "write"
        click.echo(
            click.style(
                f"WARNING: This will sync @efcnewlife.org Entra Member users into auth tables ({mode}). "
                "Existing users matched by Microsoft object id or email will be updated or linked.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Syncing Microsoft Graph users...", fg="cyan"))
    asyncio.run(
        sync_microsoft_users(
            dry_run=dry_run,
            filter_expr=filter_expr,
        )
    )
    click.echo(click.style("Done.", fg="green"))
