"""
RBAC initialization CLI commands.
"""
import asyncio

import click

from portal.application.cli.rbac_seed_service import run_rbac_seed
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


def init_rbac_process():
    """Synchronous entry to run RBAC initialization."""
    click.echo(click.style("Initializing RBAC (verbs, resources, permissions, roles)...", fg="cyan"))
    asyncio.run(init_rbac())
    click.echo(click.style("Done.", fg="green"))
