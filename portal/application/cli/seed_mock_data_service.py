"""
`seed-mock-data` orchestration: complete the near-term Facility Booking QA
fixture suite for the current local Mock inventory (ADR 0025) — weekly slot
templates, campus-wide and room-specific Blackouts, ten confirmed Bookings,
an Owner-position incumbent, and a pending Ministry Application.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

import click
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import MockSeedInventoryError, find_local_archive_pair, parse_mock_run_identity, read_csv_rows
from portal.application.cli.mock_fixture_plans import (
    BOOKING_PLACEMENT_WINDOW_DAYS,
    CAMPUS_BLACKOUT_END,
    CAMPUS_BLACKOUT_LABEL,
    CAMPUS_BLACKOUT_START,
    MOCK_FIXTURE_TIMEZONE,
    ROOM_BLACKOUT_END,
    ROOM_BLACKOUT_LABEL,
    ROOM_BLACKOUT_ROOM_CODE,
    ROOM_BLACKOUT_START,
    SLOT_TEMPLATE_LABEL,
    ExistingBlackout,
    OccupyingInterval,
    build_mock_booking_plans,
    mock_fixture_name,
    place_booking_plan,
    place_campus_blackout,
    place_room_blackout,
    slot_template_mask,
)
from portal.application.cli.mock_locale_lookup import resolve_default_locale_id
from portal.application.cli.mock_ministry_inventory import MOCK_MINISTRY_COUNT, ministry_purpose
from portal.application.cli.mock_user_persona import PERSONA_OWNER, PERSONA_PERSONAL, PERSONA_STEWARD
from portal.domain.facility.constants import BookingSlotStatus, BookingStatus, BookingType, RoomBlackoutKind
from portal.domain.org.constants import MinistryApprovalStatus, MinistryMemberRole, MinistryStatus
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.libs.database import Session
from portal.models import (
    AuthUser,
    FacilityBooking,
    FacilityBookingRoom,
    FacilityBookingSlot,
    FacilityRoom,
    FacilityRoomBlackout,
    FacilityRoomSlotTemplate,
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistryTranslation,
    OrgPosition,
)

MINISTRY_TYPE_SCHEMA_ERROR = (
    "Ministry Type is required (NOT NULL) by this database. seed-mock-data needs the optional-Ministry-Type "
    "schema revision (migration 66fd53b703c7) applied before it can create a Ministry Application without a Ministry Type."
)

REQUIRED_PERSONAL_COUNT = 5
REQUIRED_STEWARD_COUNT = 3
REQUIRED_OWNER_COUNT = 1
REQUIRED_PERSONAS = (PERSONA_PERSONAL, PERSONA_STEWARD, PERSONA_OWNER)

Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class MockDataPrerequisiteError(ValueError):
    """Raised when a Mock inventory row, account, Ministry, or catalog prerequisite is missing or invalid."""


class MockFixturePlacementError(MockDataPrerequisiteError):
    """Raised when the complete Mock fixture suite cannot be placed in the 30-day window."""


@dataclass(frozen=True)
class SeedMockDataResult:
    run_identity: str
    slot_template_count: int
    blackout_count: int
    booking_count: int
    owner_position_id: UUID
    owner_position_code: str
    ministry_application_id: UUID
    ministry_application_name: str


def _as_uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _rows_by_persona(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        persona = (row.get("persona") or "").strip()
        if persona:
            grouped[persona].append(row)
    return grouped


def _row_value(row: object, key: str):
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key)


class SeedMockDataService:
    """Complete the near-term Facility Booking QA fixture suite for the current Mock inventory."""

    def __init__(self, session: Session, *, env: str, default_locale_code: str, output_dir: Path, clock: Clock = _default_clock):
        self._session = session
        self._env = env
        self._default_locale_code = default_locale_code
        self._output_dir = output_dir
        self._clock = clock

    async def _resolve_user_id(self, email: str, *, label: str) -> UUID:
        user_id = await self._session.select(AuthUser.id).where(AuthUser.email == email).fetchval()
        if not user_id:
            raise MockDataPrerequisiteError(f"{label} Mock user {email!r} not found. Run seed-mock-users first.")
        return _as_uuid(user_id)

    async def _active_rooms(self) -> dict[str, UUID]:
        rows = await (
            self._session.select(FacilityRoom.id, FacilityRoom.code)
            .where(FacilityRoom.is_active == True)
            .where(FacilityRoom.is_deleted == False)
            .order_by(FacilityRoom.sequence)
            .fetch()
        )
        rooms = {str(_row_value(row, "code")): _as_uuid(_row_value(row, "id")) for row in rows or []}
        if not rooms:
            raise MockDataPrerequisiteError("No active facility room found. Run seed-facility-rental first.")
        return rooms

    async def _first_owning_position(self) -> tuple[UUID, str]:
        row = await (
            self._session.select(OrgPosition.id, OrgPosition.code)
            .where(OrgPosition.can_own_ministry == True)
            .where(OrgPosition.is_active == True)
            .where(OrgPosition.is_deleted == False)
            .order_by(OrgPosition.sequence)
            .limit(1)
            .fetchrow()
        )
        if not row:
            raise MockDataPrerequisiteError("No active position with can_own_ministry found. Run seed-positions first.")
        return _as_uuid(row["id"]), row["code"]

    async def _load_occupancy(self) -> list[OccupyingInterval]:
        rows = await (
            self._session.select(FacilityBookingSlot.facility_id, FacilityBookingSlot.start_at, FacilityBookingSlot.end_at)
            .where(FacilityBookingSlot.status == BookingSlotStatus.CONFIRMED.value)
            .fetch()
        )
        occupancy: list[OccupyingInterval] = []
        for row in rows or []:
            occupancy.append(
                OccupyingInterval(facility_id=_as_uuid(_row_value(row, "facility_id")), start_at=_row_value(row, "start_at"), end_at=_row_value(row, "end_at"))
            )
        return occupancy

    async def _load_blackouts(self) -> list[ExistingBlackout]:
        rows = await (
            self._session.select(
                FacilityRoomBlackout.facility_id,
                FacilityRoomBlackout.kind,
                FacilityRoomBlackout.blackout_date,
                FacilityRoomBlackout.days_of_week_mask,
                FacilityRoomBlackout.start_time,
                FacilityRoomBlackout.end_time,
                FacilityRoomBlackout.effective_from,
                FacilityRoomBlackout.effective_to,
            )
            .where(FacilityRoomBlackout.is_active == True)
            .where(FacilityRoomBlackout.is_deleted == False)
            .fetch()
        )
        blackouts: list[ExistingBlackout] = []
        for row in rows or []:
            facility_id = _row_value(row, "facility_id")
            blackouts.append(
                ExistingBlackout(
                    facility_id=_as_uuid(facility_id) if facility_id is not None else None,
                    kind=str(_row_value(row, "kind")),
                    blackout_date=_row_value(row, "blackout_date"),
                    days_of_week_mask=_row_value(row, "days_of_week_mask"),
                    start_time=_row_value(row, "start_time"),
                    end_time=_row_value(row, "end_time"),
                    effective_from=_row_value(row, "effective_from"),
                    effective_to=_row_value(row, "effective_to"),
                )
            )
        return blackouts

    async def _insert_slot_templates(self, *, rooms: dict[str, UUID], run_identity: str) -> int:
        name = mock_fixture_name(SLOT_TEMPLATE_LABEL, run_identity)
        mask = slot_template_mask()
        count = 0
        for facility_id in rooms.values():
            await (
                self._session.insert(FacilityRoomSlotTemplate)
                .values(
                    id=uuid.uuid4(),
                    facility_id=facility_id,
                    name=name,
                    days_of_week_mask=mask,
                    start_time=time(8, 0),
                    end_time=time(22, 0),
                    slot_duration_minutes=60,
                    is_active=True,
                )
                .execute()
            )
            count += 1
        return count

    async def _insert_blackout(self, *, facility_id: Optional[UUID], label: str, run_identity: str, blackout_date, start_time, end_time, reason: str) -> None:
        await (
            self._session.insert(FacilityRoomBlackout)
            .values(
                id=uuid.uuid4(),
                facility_id=facility_id,
                name=mock_fixture_name(label, run_identity),
                reason=reason,
                kind=RoomBlackoutKind.ONE_OFF.value,
                blackout_date=blackout_date,
                days_of_week_mask=None,
                start_time=start_time,
                end_time=end_time,
                is_active=True,
            )
            .execute()
        )

    async def _insert_booking(
        self, *, user_id: UUID, ministry_id: Optional[UUID], room_ids: list[UUID], start_at: datetime, end_at: datetime, remark: str, title: str
    ) -> UUID:
        booking_id = uuid.uuid4()
        await (
            self._session.insert(FacilityBooking)
            .values(
                id=booking_id,
                user_id=user_id,
                facility_id=room_ids[0],
                ministry_id=ministry_id,
                booking_type=BookingType.ONE_TIME.value,
                start_at=start_at,
                end_at=end_at,
                status=BookingStatus.CONFIRMED.value,
                remark=remark,
                title=title,
                created_by_id=user_id,
            )
            .execute()
        )
        for sequence, room_id in enumerate(room_ids):
            await (
                self._session.insert(FacilityBookingRoom)
                .values(id=uuid.uuid4(), facility_booking_id=booking_id, facility_id=room_id, sequence=sequence, start_at=start_at, end_at=end_at)
                .execute()
            )
            await (
                self._session.insert(FacilityBookingSlot)
                .values(
                    id=uuid.uuid4(),
                    facility_booking_id=booking_id,
                    facility_id=room_id,
                    start_at=start_at,
                    end_at=end_at,
                    status=BookingSlotStatus.CONFIRMED.value,
                )
                .execute()
            )
        return booking_id

    def _read_inventory(self) -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]], str]:
        account_csv, ministry_csv = find_local_archive_pair(self._output_dir, env=self._env)
        account_rows = _rows_by_persona(read_csv_rows(account_csv))
        missing_personas = [persona for persona in REQUIRED_PERSONAS if persona not in account_rows]
        if missing_personas:
            raise MockDataPrerequisiteError(f"Mock inventory {account_csv} is missing persona(s): {', '.join(missing_personas)}.")
        if len(account_rows[PERSONA_PERSONAL]) != REQUIRED_PERSONAL_COUNT:
            raise MockDataPrerequisiteError(f"Mock inventory {account_csv} must contain {REQUIRED_PERSONAL_COUNT} personal Testing accounts.")
        if len(account_rows[PERSONA_STEWARD]) != REQUIRED_STEWARD_COUNT:
            raise MockDataPrerequisiteError(f"Mock inventory {account_csv} must contain {REQUIRED_STEWARD_COUNT} steward Testing accounts.")
        if len(account_rows[PERSONA_OWNER]) != REQUIRED_OWNER_COUNT:
            raise MockDataPrerequisiteError(f"Mock inventory {account_csv} must contain {REQUIRED_OWNER_COUNT} owner Testing account.")

        ministry_rows = read_csv_rows(ministry_csv)
        if len(ministry_rows) != MOCK_MINISTRY_COUNT:
            raise MockDataPrerequisiteError(
                f"Mock Ministry inventory {ministry_csv} must contain exactly {MOCK_MINISTRY_COUNT} rows; found {len(ministry_rows)}."
            )
        for ministry_row in ministry_rows:
            if not (ministry_row.get("ministry_code") or "").strip() or not (ministry_row.get("ministry_name") or "").strip():
                raise MockDataPrerequisiteError(f"Mock Ministry inventory {ministry_csv} is missing ministry_code/ministry_name.")

        run_identity = parse_mock_run_identity(account_csv, env=self._env)
        return account_rows, ministry_rows, run_identity

    async def _resolve_ministry_id(self, ministry_name: str) -> UUID:
        ministry_id = await self._session.select(OrgMinistryTranslation.ministry_id).where(OrgMinistryTranslation.name == ministry_name).fetchval()
        if not ministry_id:
            raise MockDataPrerequisiteError(f"Mock Ministry {ministry_name!r} not found. Run seed-mock-users first.")
        return _as_uuid(ministry_id)

    def _ministry_name_for_label(self, ministry_rows: list[dict[str, str]], label: str) -> str:
        expected_purpose = ministry_purpose(label)
        for row in ministry_rows:
            if (row.get("purpose") or "").strip() == expected_purpose:
                return row["ministry_name"].strip()
        raise MockDataPrerequisiteError(f"Mock Ministry inventory is missing the {label!r} Ministry.")

    async def run(self) -> SeedMockDataResult:
        try:
            account_rows, ministry_rows, run_identity = self._read_inventory()
        except MockSeedInventoryError as exc:
            raise MockDataPrerequisiteError(str(exc)) from exc

        personal_ids = [
            await self._resolve_user_id(row["email"], label=f"{PERSONA_PERSONAL.capitalize()}[{index}]")
            for index, row in enumerate(account_rows[PERSONA_PERSONAL])
        ]
        steward_ids = [
            await self._resolve_user_id(row["email"], label=f"{PERSONA_STEWARD.capitalize()}[{index}]")
            for index, row in enumerate(account_rows[PERSONA_STEWARD])
        ]
        owner_id = await self._resolve_user_id(account_rows[PERSONA_OWNER][0]["email"], label=PERSONA_OWNER.capitalize())

        locale_id = await resolve_default_locale_id(self._session, self._default_locale_code)
        if not locale_id:
            raise MockDataPrerequisiteError(f"Locale {self._default_locale_code!r} not found or inactive. Run init-all (or init-locales) first.")

        rooms = await self._active_rooms()
        owner_position_id, owner_position_code = await self._first_owning_position()
        occupancy = await self._load_occupancy()
        blackouts = await self._load_blackouts()
        now = self._clock()
        today = now.astimezone(MOCK_FIXTURE_TIMEZONE).date()
        all_facility_ids = list(rooms.values())

        campus_day = place_campus_blackout(today=today, occupancy=occupancy, blackouts=blackouts, all_facility_ids=all_facility_ids)
        if campus_day is None:
            raise MockFixturePlacementError(
                f"No available campus-wide Blackout day in the next {BOOKING_PLACEMENT_WINDOW_DAYS} days. The complete fixture suite was not created."
            )
        blackouts.append(
            ExistingBlackout(
                facility_id=None,
                kind=RoomBlackoutKind.ONE_OFF.value,
                blackout_date=campus_day,
                days_of_week_mask=None,
                start_time=CAMPUS_BLACKOUT_START,
                end_time=CAMPUS_BLACKOUT_END,
            )
        )

        sanctuary_id = rooms.get(ROOM_BLACKOUT_ROOM_CODE)
        if sanctuary_id is None:
            raise MockDataPrerequisiteError(f"Room code {ROOM_BLACKOUT_ROOM_CODE!r} not found. Run seed-facility-rental first.")
        room_day = place_room_blackout(today=today, occupancy=occupancy, blackouts=blackouts, facility_id=sanctuary_id, excluded_dates={campus_day})
        if room_day is None:
            raise MockFixturePlacementError(
                f"No available room-specific Blackout day in the next {BOOKING_PLACEMENT_WINDOW_DAYS} days. The complete fixture suite was not created."
            )
        blackouts.append(
            ExistingBlackout(
                facility_id=sanctuary_id,
                kind=RoomBlackoutKind.ONE_OFF.value,
                blackout_date=room_day,
                days_of_week_mask=None,
                start_time=ROOM_BLACKOUT_START,
                end_time=ROOM_BLACKOUT_END,
            )
        )

        ministry_ids_by_name: dict[str, UUID] = {}
        placed_bookings = []
        booker_ids = {PERSONA_PERSONAL: personal_ids, PERSONA_STEWARD: steward_ids}
        for plan in build_mock_booking_plans():
            missing_rooms = [code for code in plan.room_codes if code not in rooms]
            if missing_rooms:
                raise MockDataPrerequisiteError(f"Room code {missing_rooms[0]!r} not found. Run seed-facility-rental first.")
            facility_ids = [rooms[code] for code in plan.room_codes]
            placed = place_booking_plan(plan, today=today, occupancy=occupancy, blackouts=blackouts, facility_ids=facility_ids)
            if placed is None:
                raise MockFixturePlacementError(
                    f"No available slot in the next {BOOKING_PLACEMENT_WINDOW_DAYS} days for Mock booking scenario {plan.title!r}. "
                    "The complete fixture suite was not created."
                )
            placed_bookings.append(placed)
            for facility_id in facility_ids:
                occupancy.append(OccupyingInterval(facility_id=facility_id, start_at=placed.start_at, end_at=placed.end_at))

        slot_template_count = await self._insert_slot_templates(rooms=rooms, run_identity=run_identity)
        await self._insert_blackout(
            facility_id=None,
            label=CAMPUS_BLACKOUT_LABEL,
            run_identity=run_identity,
            blackout_date=campus_day,
            start_time=CAMPUS_BLACKOUT_START,
            end_time=CAMPUS_BLACKOUT_END,
            reason="Mock campus-wide holiday closure",
        )
        await self._insert_blackout(
            facility_id=sanctuary_id,
            label=ROOM_BLACKOUT_LABEL,
            run_identity=run_identity,
            blackout_date=room_day,
            start_time=ROOM_BLACKOUT_START,
            end_time=ROOM_BLACKOUT_END,
            reason="Mock sanctuary maintenance window",
        )

        for placed in placed_bookings:
            plan = placed.plan
            ministry_id = None
            if plan.ministry_label is not None:
                ministry_name = self._ministry_name_for_label(ministry_rows, plan.ministry_label)
                ministry_id = ministry_ids_by_name.get(ministry_name)
                if ministry_id is None:
                    ministry_id = await self._resolve_ministry_id(ministry_name)
                    ministry_ids_by_name[ministry_name] = ministry_id
            booker_id = booker_ids[plan.booker_persona][plan.booker_index]
            await self._insert_booking(
                user_id=booker_id,
                ministry_id=ministry_id,
                room_ids=[rooms[code] for code in plan.room_codes],
                start_at=placed.start_at,
                end_at=placed.end_at,
                remark=f"Mock QA: {plan.title}",
                title=plan.title,
            )

        await PositionRepository(self._session).assign_incumbent(position_id=owner_position_id, user_id=owner_id)

        application_id = uuid.uuid4()
        application_name = f"Mock Ministry Application ({run_identity})"
        try:
            await (
                self._session.insert(OrgMinistry)
                .values(
                    id=application_id,
                    ministry_type_id=None,
                    owner_position_id=owner_position_id,
                    status=MinistryStatus.PENDING_APPROVAL.value,
                    is_active=True,
                    has_priority_booking=False,
                    submitted_at=now,
                    submitted_by_id=steward_ids[0],
                    created_by_id=steward_ids[0],
                )
                .execute()
            )
        except NotNullViolationError as exc:
            raise RuntimeError(MINISTRY_TYPE_SCHEMA_ERROR) from exc

        await (
            self._session.insert(OrgMinistryTranslation)
            .values(id=uuid.uuid4(), ministry_id=application_id, locale_id=locale_id, name=application_name)
            .execute()
        )
        await (
            self._session.insert(OrgMinistryMember)
            .values(id=uuid.uuid4(), ministry_id=application_id, user_id=steward_ids[0], member_role=MinistryMemberRole.PRIMARY.value)
            .execute()
        )
        await (
            self._session.insert(OrgMinistryApproval)
            .values(
                id=uuid.uuid4(),
                ministry_id=application_id,
                owner_position_id=owner_position_id,
                status=MinistryApprovalStatus.PENDING.value,
                requested_by_id=steward_ids[0],
            )
            .execute()
        )

        await self._session.commit()
        click.echo(
            click.style(
                f"Mock data committed ({run_identity}): {slot_template_count} slot template(s), 2 Blackouts, {len(placed_bookings)} Bookings, "
                f"Owner assigned to {owner_position_code!r}, and Ministry Application {application_name!r} pending that Owner's decision.",
                fg="green",
            )
        )

        return SeedMockDataResult(
            run_identity=run_identity,
            slot_template_count=slot_template_count,
            blackout_count=2,
            booking_count=len(placed_bookings),
            owner_position_id=owner_position_id,
            owner_position_code=owner_position_code,
            ministry_application_id=application_id,
            ministry_application_name=application_name,
        )
