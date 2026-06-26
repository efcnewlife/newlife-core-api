"""
RBAC initialization CLI commands.
"""
import asyncio

import click

from portal.application.cli.rbac_seed_service import run_rbac_reset, run_rbac_seed
from portal.config import settings
from portal.container import Container


async def init_rbac():
    """
    Seed verbs, resources, permissions, roles, and role-permission mappings.
    """
    container = Container()
    session = container.db_session()
    try:
        await run_rbac_seed(session)
    finally:
        await session.close()


async def reset_rbac():
    """
    Delete all RBAC data and re-seed from rbac_seed_data.
    """
    container = Container()
    session = container.db_session()
    try:
        await run_rbac_reset(session)
    finally:
        await session.close()


def init_rbac_process():
    """Synchronous entry to run RBAC initialization."""
    click.echo(click.style("Initializing RBAC (verbs, resources, permissions, roles)...", fg="cyan"))
    asyncio.run(init_rbac())
    click.echo(click.style("Done.", fg="green"))


def reset_rbac_process(*, force: bool = False):
    """Synchronous entry to wipe and re-seed RBAC data."""
    if not settings.IS_DEV and not force:
        click.echo(
            click.style(
                f"reset-rbac is blocked when ENV={settings.ENV!r}. Pass --force to proceed.",
                fg="red",
            )
        )
        raise SystemExit(1)

    if not force:
        click.echo(
            click.style(
                "WARNING: This deletes ALL RBAC data (verbs, resources, permissions, roles, "
                "translations, role-permission mappings, and user-role assignments) "
                "and re-seeds from rbac_seed_data.",
                fg="yellow",
            )
        )
        if not click.confirm("Continue?", default=False):
            click.echo("Aborted.")
            raise SystemExit(0)

    click.echo(click.style("Resetting RBAC (clear + re-seed)...", fg="cyan"))
    asyncio.run(reset_rbac())
    click.echo(click.style("Done.", fg="green"))
