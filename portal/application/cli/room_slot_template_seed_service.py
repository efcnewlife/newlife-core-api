"""
Default Room Slot Template seed use case for CLI (gap-fill only).
"""

import uuid
from typing import Any

import click

from portal.domain.facility.days_of_week_mask import days_to_mask
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import FacilityRoom, FacilityRoomSlotTemplate


class RoomSlotTemplateSeedService:
    """Insert default opening hours for seeded rooms that have no Room Slot Template; never touch existing templates."""

    def __init__(self, session: Session):
        self._session = session

    async def run(self, *, room_codes: list[str], template_rows: list[dict[str, Any]]) -> int:
        rooms = (
            await self._session.select(FacilityRoom.id, FacilityRoom.code)
            .where(FacilityRoom.code.in_(room_codes))
            .where(FacilityRoom.is_deleted == False)
            .fetch()
        )
        rooms_with_templates = set(
            await self._session.select(FacilityRoomSlotTemplate.facility_id).where(FacilityRoomSlotTemplate.is_deleted == False).distinct().fetchvals()
        )
        inserted = 0
        filled_rooms = 0
        for room in rooms:
            if room["id"] in rooms_with_templates:
                continue
            for row in template_rows:
                await (
                    self._session.insert(FacilityRoomSlotTemplate)
                    .values(
                        id=uuid.uuid4(),
                        facility_id=room["id"],
                        name=row["name"],
                        days_of_week_mask=days_to_mask(row["days"]),
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        slot_duration_minutes=row["slot_duration_minutes"],
                        is_active=True,
                        effective_from=None,
                        effective_to=None,
                    )
                    .execute()
                )
                inserted += 1
            filled_rooms += 1
        await self._session.commit()
        skipped_rooms = len(rooms) - filled_rooms
        click.echo(click.style(f"Room slot templates seeded. inserted={inserted} rooms_filled={filled_rooms} rooms_skipped={skipped_rooms}", fg="bright_green"))
        logger.info("Room slot template seed completed. inserted=%s rooms_filled=%s rooms_skipped=%s", inserted, filled_rooms, skipped_rooms)
        return inserted
