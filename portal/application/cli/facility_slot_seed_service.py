"""
Facility slot template and blackout seed use case for CLI.
"""

import uuid
from typing import Any, Optional
from uuid import UUID

import click

from portal.cli.datas.facility_slot_seed_data import SEED_NAME_PREFIX
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import FacilityRoom, FacilityRoomBlackout, FacilityRoomSlotTemplate


async def _load_room_ids_by_code(session: Session) -> dict[str, UUID]:
    rows = await session.select(FacilityRoom.id, FacilityRoom.code).where(FacilityRoom.is_deleted == False).fetch()
    result: dict[str, UUID] = {}
    for row in rows or []:
        code = row["code"] if isinstance(row, dict) else row.code
        room_id = row["id"] if isinstance(row, dict) else row.id
        result[str(code)] = room_id if isinstance(room_id, UUID) else UUID(str(room_id))
    return result


async def _clear_seed_rows(session: Session) -> None:
    """Hard-delete only demo rows whose name starts with the seed prefix."""
    pattern = f"{SEED_NAME_PREFIX}%"
    await session.delete(FacilityRoomBlackout).where(FacilityRoomBlackout.name.like(pattern)).execute()
    await session.delete(FacilityRoomSlotTemplate).where(FacilityRoomSlotTemplate.name.like(pattern)).execute()


async def run_facility_slot_seed(session: Session, *, slot_rows: list[dict[str, Any]], blackout_rows: list[dict[str, Any]]) -> None:
    """
    Replace ``seed:``-prefixed slot templates and blackouts, then insert demo rows.

    Looks up rooms by stable code. Missing rooms are skipped with a warning.
    """
    room_ids = await _load_room_ids_by_code(session)
    await _clear_seed_rows(session)

    skipped_codes: set[str] = set()
    slots_inserted = 0
    blackouts_inserted = 0

    for row in slot_rows:
        room_code = row["room_code"]
        facility_id = room_ids.get(room_code)
        if facility_id is None:
            skipped_codes.add(room_code)
            click.echo(click.style(f"Skip slot template {row['name']!r}: room code {room_code!r} not found", fg="yellow"))
            continue
        await (
            session.insert(FacilityRoomSlotTemplate)
            .values(
                id=uuid.uuid4(),
                facility_id=facility_id,
                name=row["name"],
                days_of_week_mask=row["days_of_week_mask"],
                start_time=row["start_time"],
                end_time=row["end_time"],
                slot_duration_minutes=row["slot_duration_minutes"],
                is_active=row.get("is_active", True),
                effective_from=row.get("effective_from"),
                effective_to=row.get("effective_to"),
            )
            .execute()
        )
        slots_inserted += 1

    for row in blackout_rows:
        room_code: Optional[str] = row.get("room_code")
        facility_id: Optional[UUID] = None
        if room_code is not None:
            facility_id = room_ids.get(room_code)
            if facility_id is None:
                skipped_codes.add(room_code)
                click.echo(click.style(f"Skip blackout {row['name']!r}: room code {room_code!r} not found", fg="yellow"))
                continue
        await (
            session.insert(FacilityRoomBlackout)
            .values(
                id=uuid.uuid4(),
                facility_id=facility_id,
                name=row["name"],
                reason=row["reason"],
                kind=row["kind"],
                blackout_date=row.get("blackout_date"),
                days_of_week_mask=row.get("days_of_week_mask"),
                start_time=row["start_time"],
                end_time=row["end_time"],
                is_active=row.get("is_active", True),
                effective_from=row.get("effective_from"),
                effective_to=row.get("effective_to"),
            )
            .execute()
        )
        blackouts_inserted += 1

    await session.commit()
    summary = f"Facility slot seed done: {slots_inserted} slot template(s), {blackouts_inserted} blackout(s)"
    if skipped_codes:
        summary += f"; skipped room codes: {', '.join(sorted(skipped_codes))}"
    click.echo(click.style(summary, fg="green"))
    logger.info(summary)
