"""
Catalog bootstrap CLI: init-all.
"""

import click

from portal.application.cli.init_all_service import InitAllService
from portal.cli.init_locale import init_locales
from portal.cli.rbac import init_rbac
from portal.cli.seed_facility_rental import seed_facility_rental
from portal.cli.seed_legal_documents import seed_legal_documents_async
from portal.cli.seed_position import seed_positions
from portal.cli.seed_system_settings import seed_system_settings_async
from portal.cli.seed_target_audience import seed_target_audiences
from portal.cli.superuser import create_superuser_process


async def seed_facility_rental_catalog() -> None:
    """Upsert facility rooms and rates without deleting existing catalog rows."""
    await seed_facility_rental(reset=False)


def init_all_process() -> None:
    """Seed catalog data in fail-fast order, then run interactive superuser creation."""
    click.echo(click.style("Bootstrapping catalog data, then creating a superuser.", fg="cyan"))
    click.echo("Order: locales -> RBAC -> system settings -> positions -> target audiences -> facility rooms/rates -> Legal Documents -> create-superuser.")
    click.echo("Does not seed Ministry Types, Mock users, Ministries, or Bookings.")
    service = InitAllService(
        init_locales=init_locales,
        init_rbac=init_rbac,
        seed_system_settings=seed_system_settings_async,
        seed_positions=seed_positions,
        seed_target_audiences=seed_target_audiences,
        seed_facility_rental=seed_facility_rental_catalog,
        seed_legal_documents=seed_legal_documents_async,
        create_superuser=create_superuser_process,
    )
    service.run()
    click.echo(click.style("init-all finished.", fg="green"))
