"""
Default Room Slot Template seed CLI.
"""

import asyncio

import click

from portal.application.cli.room_slot_template_seed_service import RoomSlotTemplateSeedService
from portal.cli.datas.facility_rental_seed_data import facility_room_seed_rows
from portal.cli.datas.room_slot_template_seed_data import default_room_slot_template_seed_rows
from portal.container import Container
from portal.libs.logger import logger


async def seed_room_slot_templates_async() -> None:
    """Seed default opening hours for seeded rooms that have no Room Slot Template (gap-fill only)."""
    container = Container()
    session = container.db_session()
    try:
        service = RoomSlotTemplateSeedService(session)
        await service.run(room_codes=[row["code"] for row in facility_room_seed_rows], template_rows=default_room_slot_template_seed_rows)
    except Exception as e:
        await session.rollback()
        click.echo(click.style(f"Room slot template seed failed: {e}", fg="red"))
        logger.exception(e)
        raise
    finally:
        await session.close()


def seed_room_slot_templates_process() -> None:
    """Synchronous entry for default Room Slot Template seed."""
    asyncio.run(seed_room_slot_templates_async())
