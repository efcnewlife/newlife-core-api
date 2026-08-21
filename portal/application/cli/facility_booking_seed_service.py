"""
Facility booking demo seed use case for CLI.

Replaces bookings whose remark starts with the demo prefix and inserts confirmed
one-time bookings with rooms and occupancy slots. Does not run live pricing.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

import click

from portal.application.cli.ministry_seed_service import ensure_demo_user
from portal.cli.datas.facility_booking_seed_data import BOOKING_SEED_REMARK_PREFIX, build_demo_booking_plans
from portal.cli.datas.ministry_seed_data import SEED_NAME_PREFIX as MINISTRY_SEED_PREFIX
from portal.cli.datas.ministry_seed_data import ministry_seed_rows
from portal.domain.facility.constants import BookingSlotStatus, BookingStatus, BookingType
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import AuthUser, FacilityBooking, FacilityBookingRoom, FacilityBookingSlot, FacilityRoom, OrgMinistryTranslation

DEMO_TZ = ZoneInfo("America/Toronto")


def _demo_english_ministry_names() -> set[str]:
    return {row["translations"]["en"]["name"] for row in ministry_seed_rows}


async def _load_room_ids_by_code(session: Session) -> dict[str, UUID]:
    rows = await session.select(FacilityRoom.id, FacilityRoom.code).where(FacilityRoom.is_deleted == False).fetch()
    result: dict[str, UUID] = {}
    for row in rows or []:
        result[str(row["code"])] = row["id"] if isinstance(row["id"], UUID) else UUID(str(row["id"]))
    return result


async def _load_demo_ministry_ids_by_english_name(session: Session) -> dict[str, UUID]:
    """Map unprefixed English demo ministry names to ministry ids."""
    english_names = _demo_english_ministry_names()
    rows = await (
        session.select(OrgMinistryTranslation.ministry_id, OrgMinistryTranslation.name).where(OrgMinistryTranslation.name.in_(list(english_names))).fetch()
    )
    result: dict[str, UUID] = {}
    for row in rows or []:
        name = str(row["name"])
        unprefixed = name[len(MINISTRY_SEED_PREFIX) :] if name.startswith(MINISTRY_SEED_PREFIX) else name
        ministry_id = row["ministry_id"] if isinstance(row["ministry_id"], UUID) else UUID(str(row["ministry_id"]))
        result[unprefixed] = ministry_id
    return result


async def _clear_seed_bookings(session: Session) -> int:
    booking_ids = await session.select(FacilityBooking.id).where(FacilityBooking.remark.like(f"{BOOKING_SEED_REMARK_PREFIX}%")).fetchvals()
    unique_ids = sorted({booking_id if isinstance(booking_id, UUID) else UUID(str(booking_id)) for booking_id in booking_ids or []})
    if not unique_ids:
        return 0
    await session.delete(FacilityBooking).where(FacilityBooking.id.in_(unique_ids)).execute()
    return len(unique_ids)


def _local_range_to_utc(*, anchor: date, day_offset: int, start_hour: int, end_hour: int) -> tuple[datetime, datetime]:
    local_day = anchor + timedelta(days=day_offset)
    start_local = datetime(local_day.year, local_day.month, local_day.day, start_hour, 0, tzinfo=DEMO_TZ)
    end_local = datetime(local_day.year, local_day.month, local_day.day, end_hour, 0, tzinfo=DEMO_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


async def _resolve_booker_id(session: Session, users_by_email: dict[str, UUID], booker_email: str) -> UUID:
    if booker_email in users_by_email:
        return users_by_email[booker_email]
    existing_id = await session.select(AuthUser.id).where(AuthUser.email == booker_email).fetchval()
    if not existing_id:
        raise ValueError(f"Booker {booker_email!r} not found. Run demo ministry seed before bookings.")
    user_id = existing_id if isinstance(existing_id, UUID) else UUID(str(existing_id))
    users_by_email[booker_email] = user_id
    return user_id


async def run_facility_booking_seed(session: Session, *, personal_booker_rows: list[dict[str, Any]], today: Optional[date] = None, commit: bool = True) -> None:
    """
    Replace demo-prefixed bookings and insert confirmed demo bookings.

    Requires facility rooms and demo ministries (for ministry-linked plans) to exist.
    """
    room_ids = await _load_room_ids_by_code(session)
    if not room_ids:
        raise ValueError("No facility rooms found. Run seed-facility-rental first.")

    ministry_ids = await _load_demo_ministry_ids_by_english_name(session)
    anchor = today or datetime.now(tz=DEMO_TZ).date()
    plans = build_demo_booking_plans(today=anchor)

    users_by_email: dict[str, UUID] = {}
    for row in personal_booker_rows:
        users_by_email[row["email"]] = await ensure_demo_user(session, row)

    deleted = await _clear_seed_bookings(session)
    inserted = 0

    for plan in plans:
        booker_id = await _resolve_booker_id(session, users_by_email, plan["booker_email"])

        facility_ids: list[UUID] = []
        for room_code in plan["room_codes"]:
            facility_id = room_ids.get(room_code)
            if facility_id is None:
                raise ValueError(f"Room code {room_code!r} not found. Run seed-facility-rental first.")
            facility_ids.append(facility_id)

        ministry_id: Optional[UUID] = None
        ministry_name = plan["ministry_english_name"]
        if ministry_name is not None:
            ministry_id = ministry_ids.get(ministry_name)
            if ministry_id is None:
                raise ValueError(f"Demo ministry {ministry_name!r} not found. Run demo ministry seed before bookings.")

        start_at, end_at = _local_range_to_utc(anchor=anchor, day_offset=plan["day_offset"], start_hour=plan["start_hour"], end_hour=plan["end_hour"])
        booking_id = uuid.uuid4()

        await (
            session.insert(FacilityBooking)
            .values(
                id=booking_id,
                user_id=booker_id,
                facility_id=facility_ids[0],
                ministry_id=ministry_id,
                booking_type=BookingType.ONE_TIME.value,
                start_at=start_at,
                end_at=end_at,
                status=BookingStatus.CONFIRMED.value,
                remark=plan["remark"],
                created_by_id=booker_id,
            )
            .execute()
        )

        for sequence, facility_id in enumerate(facility_ids):
            await (
                session.insert(FacilityBookingRoom)
                .values(id=uuid.uuid4(), facility_booking_id=booking_id, facility_id=facility_id, sequence=sequence, start_at=start_at, end_at=end_at)
                .execute()
            )
            await (
                session.insert(FacilityBookingSlot)
                .values(
                    id=uuid.uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=facility_id,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
                .execute()
            )

        inserted += 1

    if commit:
        await session.commit()
    summary = f"Facility booking seed done: {inserted} booking(s) inserted, {deleted} demo booking(s) replaced"
    click.echo(click.style(summary, fg="green"))
    logger.info(summary)
