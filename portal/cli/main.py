"""
Main Click CLI entry aggregating all subcommands.
"""

import click

from .superuser import create_superuser_process
from .init_locale import init_locales_process
from .rbac import init_rbac_process, reset_rbac_process
from .seed_position import seed_positions_process


@click.group()
def cli():
    """Portal CLI"""


@cli.command(name="create-superuser")
def create_superuser_cmd():
    """Create a superuser via interactive prompts."""
    create_superuser_process()


@cli.command(name="init-rbac")
def init_rbac_cmd():
    """Initialize RBAC data (verbs/resources/permissions/roles)."""
    init_rbac_process()


@cli.command(name="reset-rbac")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
def reset_rbac_cmd(force: bool):
    """Delete all RBAC data and re-seed from rbac_seed_data."""
    reset_rbac_process(force=force)


@cli.command(name="init-locales")
def init_locales_cmd():
    """Initialize locale data."""
    init_locales_process()


@cli.command(name="seed-positions")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
def seed_positions_cmd(force: bool):
    """Seed org positions with multilingual translations."""
    seed_positions_process(force=force)


def main() -> int:
    cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

