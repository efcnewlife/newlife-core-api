"""
Main Click CLI entry aggregating all subcommands.
"""

import click

from .superuser import create_superuser_process
from .init_locale import init_locales_process
from .rbac import init_rbac_process, reset_rbac_process
from .seed_position import seed_positions_process
from .seed_ministry_type import seed_ministry_types_process
from .seed_target_audience import seed_target_audiences_process
from .seed_facility_rental import seed_facility_rental_process
from .sync_microsoft_users import sync_microsoft_users_process


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


@cli.command(name="seed-ministry-types")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
def seed_ministry_types_cmd(force: bool):
    """Seed org ministry types with multilingual translations."""
    seed_ministry_types_process(force=force)


@cli.command(name="seed-target-audiences")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
def seed_target_audiences_cmd(force: bool):
    """Seed org target audiences with multilingual translations."""
    seed_target_audiences_process(force=force)


@cli.command(name="seed-facility-rental")
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help=(
        "Hard-delete facility bookings, slot templates, rooms, rates, discounts, "
        "surcharges, and policy settings, then re-seed from seed data."
    ),
)
def seed_facility_rental_cmd(force: bool, reset: bool):
    """Seed facility rooms, rates, discounts, surcharges, and policy settings."""
    seed_facility_rental_process(force=force, reset=reset)


@cli.command(name="sync-microsoft-users")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview create/update/link counts without writing to the database.",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Skip confirmation and allow running when ENV is prod or stg.",
)
@click.option(
    "--filter",
    "filter_expr",
    default=None,
    help="Override the default OData filter for Graph /users.",
)
def sync_microsoft_users_cmd(dry_run: bool, force: bool, filter_expr: str | None):
    """Sync @efcnewlife.org Entra Member users into auth tables."""
    sync_microsoft_users_process(
        dry_run=dry_run,
        force=force,
        filter_expr=filter_expr,
    )


def main() -> int:
    cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

