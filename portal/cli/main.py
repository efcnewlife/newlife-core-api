"""
Main Click CLI entry aggregating all subcommands.
"""

import click

from .init_all import init_all_process
from .init_locale import init_locales_process
from .rbac import init_rbac_process, reset_rbac_process
from .remove_mock_data import remove_mock_data_process
from .seed_facility_rental import seed_facility_rental_process
from .seed_legal_documents import seed_legal_documents_process
from .seed_local_demo import seed_local_demo_process
from .seed_ministry_type import seed_ministry_types_process
from .seed_mock_data import seed_mock_data_process
from .seed_mock_users import seed_mock_users_process
from .seed_position import seed_positions_process
from .seed_position_assignment import seed_position_assignments_process
from .seed_system_settings import seed_system_settings_process
from .seed_target_audience import seed_target_audiences_process
from .superuser import create_superuser_process
from .sync_microsoft_users import sync_microsoft_users_process


@click.group()
def cli():
    """Portal CLI"""


@cli.command(name="init-all")
def init_all_cmd():
    """Bootstrap catalog data, then create a superuser via interactive prompts."""
    init_all_process()


@cli.command(name="create-superuser")
def create_superuser_cmd():
    """Create a superuser via interactive prompts."""
    create_superuser_process()


@cli.command(name="init-rbac")
def init_rbac_cmd():
    """Initialize RBAC data (verbs/resources/permissions/roles)."""
    init_rbac_process()


@cli.command(name="reset-rbac")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def reset_rbac_cmd(force: bool):
    """Delete all RBAC data and re-seed from rbac_seed_data."""
    reset_rbac_process(force=force)


@cli.command(name="init-locales")
def init_locales_cmd():
    """Initialize locale data."""
    init_locales_process()


@cli.command(name="seed-positions")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def seed_positions_cmd(force: bool):
    """Seed org positions with multilingual translations."""
    seed_positions_process(force=force)


@cli.command(name="seed-position-assignments")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def seed_position_assignments_cmd(force: bool):
    """Bind users to org positions as incumbents (by email and position code)."""
    seed_position_assignments_process(force=force)


@cli.command(name="seed-ministry-types")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def seed_ministry_types_cmd(force: bool):
    """Seed org ministry types with multilingual translations."""
    seed_ministry_types_process(force=force)


@cli.command(name="seed-target-audiences")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def seed_target_audiences_cmd(force: bool):
    """Seed org target audiences with multilingual translations."""
    seed_target_audiences_process(force=force)


@cli.command(name="seed-facility-rental")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
@click.option(
    "--reset",
    is_flag=True,
    default=False,
    help=("Hard-delete facility bookings, blackouts, slot templates, rooms, rates, discounts, and surcharges, then re-seed from seed data."),
)
def seed_facility_rental_cmd(force: bool, reset: bool):
    """Seed facility rooms, rates, discounts, and surcharges."""
    seed_facility_rental_process(force=force, reset=reset)


@cli.command(name="seed-mock-users")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation; required to run in staging. Never allowed in production.")
def seed_mock_users_cmd(force: bool):
    """Create the complete Mock Testing-account and Ministry inventory, then archive the CSV pair."""
    seed_mock_users_process(force=force)


@cli.command(name="seed-mock-data")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation; required to run in staging. Never allowed in production.")
def seed_mock_data_cmd(force: bool):
    """Complete Facility Booking QA fixtures (slots, Blackouts, Bookings, Owner assignment, Ministry Application) for the current Mock inventory."""
    seed_mock_data_process(force=force)


@cli.command(name="remove-mock-data")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation; required to run in staging. Never allowed in production.")
def remove_mock_data_cmd(force: bool):
    """Delete every @test.local Mock user and its derived QA data (Bookings, Drafts, Ministries); catalog data is preserved."""
    remove_mock_data_process(force=force)


@cli.command(name="seed-local-demo")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
def seed_local_demo_cmd(force: bool):
    """Seed demo ministries, slots/blackouts, and bookings (catalog must already exist)."""
    seed_local_demo_process(force=force)


@cli.command(name="seed-system-settings")
def seed_system_settings_cmd():
    """Seed system settings (insert-if-missing; never overwrite existing values)."""
    seed_system_settings_process()


@cli.command(name="seed-legal-documents")
def seed_legal_documents_cmd():
    """Seed Legal Documents (insert-if-missing for built-in Product x Kind pairs)."""
    seed_legal_documents_process()


@cli.command(name="sync-microsoft-users")
@click.option("--dry-run", is_flag=True, default=False, help="Preview create/update/link counts without writing to the database.")
@click.option("--force", is_flag=True, default=False, help="Skip confirmation and allow running when ENV is prod or stg.")
@click.option("--filter", "filter_expr", default=None, help="Override the default OData filter for Graph /users.")
def sync_microsoft_users_cmd(dry_run: bool, force: bool, filter_expr: str | None):
    """Sync @efcnewlife.org Entra Member users into auth tables."""
    sync_microsoft_users_process(dry_run=dry_run, force=force, filter_expr=filter_expr)


def main() -> int:
    cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
