"""
`seed-mock-data` orchestration: complete the Facility Booking QA scenarios for the
current local Mock user inventory (ADR 0025) — a personal Rental Booking, an Active
steward Ministry with a Church Activity Booking, an Owner-position incumbent, and a
pending Ministry Application awaiting that Owner's decision.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional
from uuid import UUID

import click
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import MockSeedInventoryError, find_local_archive_pair, read_csv_rows
from portal.application.cli.mock_locale_lookup import resolve_default_locale_id
from portal.application.cli.mock_user_persona import PERSONA_OWNER, PERSONA_PERSONAL, PERSONA_STEWARD
from portal.domain.facility.constants import BookingSlotStatus, BookingStatus, BookingType
from portal.domain.org.constants import MinistryApprovalStatus, MinistryMemberRole, MinistryStatus
from portal.infrastructure.persistence.repositories.org.position_repository import PositionRepository
from portal.libs.database import Session
from portal.models import (
    AuthUser,
    FacilityBooking,
    FacilityBookingRoom,
    FacilityBookingSlot,
    FacilityRoom,
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistryTranslation,
    OrgPosition,
)

# The steward Ministry created by seed-mock-users has no owner_position_id, so activating it here
# has no real incumbent to record as approver (ADR 0025: Mock data bypasses the real submit/approve
# workflow). approved_by_id stays unset rather than attributing approval to the submitting steward,
# which portal/application/org/ministry_approval_service.py never allows (only an owner-position
# incumbent may approve, never the applicant).
STEWARD_MINISTRY_APPROVAL_COMMENT = "Simulated approval (seed-mock-data)"

MINISTRY_TYPE_SCHEMA_ERROR = (
    "Ministry Type is required (NOT NULL) by this database. seed-mock-data needs the optional-Ministry-Type "
    "schema revision (migration 66fd53b703c7) applied before it can create a Ministry Application without a Ministry Type."
)

REQUIRED_PERSONAS = (PERSONA_PERSONAL, PERSONA_STEWARD, PERSONA_OWNER)

Clock = Callable[[], datetime]


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class MockDataPrerequisiteError(ValueError):
    """Raised when a Mock inventory row, account, Ministry, or catalog prerequisite is missing or invalid."""


@dataclass(frozen=True)
class SeedMockDataResult:
    ministry_id: UUID
    ministry_name: str
    personal_rental_booking_id: UUID
    church_activity_booking_id: UUID
    owner_position_id: UUID
    owner_position_code: str
    ministry_application_id: UUID
    ministry_application_name: str


def _as_uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _persona_rows_by_name(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    by_persona: dict[str, dict[str, str]] = {}
    for row in rows:
        persona = (row.get("persona") or "").strip()
        if persona:
            by_persona[persona] = row
    return by_persona


class SeedMockDataService:
    """Complete the Facility Booking QA scenarios for the current local Mock user inventory."""

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

    async def _resolve_draft_ministry(self, *, ministry_name: str, steward_email: str, steward_id: UUID) -> UUID:
        ministry_id = await self._session.select(OrgMinistryTranslation.ministry_id).where(OrgMinistryTranslation.name == ministry_name).fetchval()
        if not ministry_id:
            raise MockDataPrerequisiteError(f"Steward Ministry {ministry_name!r} not found. Run seed-mock-users first.")
        ministry_id = _as_uuid(ministry_id)

        status = await self._session.select(OrgMinistry.status).where(OrgMinistry.id == ministry_id).fetchval()
        if status != MinistryStatus.DRAFT.value:
            raise MockDataPrerequisiteError(
                f"Steward Ministry {ministry_name!r} is not in draft status (currently {status!r}); seed-mock-data has likely already run "
                "for this inventory. Run seed-mock-users again for a fresh inventory."
            )

        is_member = await (
            self._session.select(OrgMinistryMember.user_id)
            .where(OrgMinistryMember.ministry_id == ministry_id)
            .where(OrgMinistryMember.user_id == steward_id)
            .fetchval()
        )
        if not is_member:
            raise MockDataPrerequisiteError(f"Steward {steward_email!r} is not a member of Ministry {ministry_name!r}.")
        return ministry_id

    async def _first_active_room_id(self) -> UUID:
        room_id = await (
            self._session.select(FacilityRoom.id)
            .where(FacilityRoom.is_active == True)
            .where(FacilityRoom.is_deleted == False)
            .order_by(FacilityRoom.sequence)
            .limit(1)
            .fetchval()
        )
        if not room_id:
            raise MockDataPrerequisiteError("No active facility room found. Run seed-facility-rental first.")
        return _as_uuid(room_id)

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

    async def _insert_booking(
        self, *, user_id: UUID, ministry_id: Optional[UUID], room_id: UUID, start_at: datetime, end_at: datetime, remark: str, title: str
    ) -> UUID:
        booking_id = uuid.uuid4()
        await (
            self._session.insert(FacilityBooking)
            .values(
                id=booking_id,
                user_id=user_id,
                facility_id=room_id,
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
        await (
            self._session.insert(FacilityBookingRoom)
            .values(id=uuid.uuid4(), facility_booking_id=booking_id, facility_id=room_id, sequence=0, start_at=start_at, end_at=end_at)
            .execute()
        )
        await (
            self._session.insert(FacilityBookingSlot)
            .values(
                id=uuid.uuid4(), facility_booking_id=booking_id, facility_id=room_id, start_at=start_at, end_at=end_at, status=BookingSlotStatus.CONFIRMED.value
            )
            .execute()
        )
        return booking_id

    def _read_inventory(self) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
        account_csv, ministry_csv = find_local_archive_pair(self._output_dir, env=self._env)
        account_rows = _persona_rows_by_name(read_csv_rows(account_csv))
        missing_personas = [persona for persona in REQUIRED_PERSONAS if persona not in account_rows]
        if missing_personas:
            raise MockDataPrerequisiteError(f"Mock inventory {account_csv} is missing persona(s): {', '.join(missing_personas)}.")

        ministry_rows = read_csv_rows(ministry_csv)
        if len(ministry_rows) != 1:
            raise MockDataPrerequisiteError(f"Mock Ministry inventory {ministry_csv} must contain exactly one row; found {len(ministry_rows)}.")
        ministry_row = ministry_rows[0]
        if not (ministry_row.get("ministry_code") or "").strip() or not (ministry_row.get("ministry_name") or "").strip():
            raise MockDataPrerequisiteError(f"Mock Ministry inventory {ministry_csv} is missing ministry_code/ministry_name.")

        steward_email = account_rows[PERSONA_STEWARD]["email"].strip().lower()
        if (ministry_row.get("primary_steward_email") or "").strip().lower() != steward_email:
            raise MockDataPrerequisiteError(f"Mock Ministry inventory {ministry_csv} primary_steward_email does not match the steward account inventory.")

        return account_rows, ministry_row

    async def run(self) -> SeedMockDataResult:
        try:
            account_rows, ministry_row = self._read_inventory()
        except MockSeedInventoryError as exc:
            raise MockDataPrerequisiteError(str(exc)) from exc

        ministry_code = ministry_row["ministry_code"].strip()
        ministry_name = ministry_row["ministry_name"].strip()

        personal_id = await self._resolve_user_id(account_rows[PERSONA_PERSONAL]["email"], label=PERSONA_PERSONAL.capitalize())
        steward_id = await self._resolve_user_id(account_rows[PERSONA_STEWARD]["email"], label=PERSONA_STEWARD.capitalize())
        owner_id = await self._resolve_user_id(account_rows[PERSONA_OWNER]["email"], label=PERSONA_OWNER.capitalize())

        locale_id = await resolve_default_locale_id(self._session, self._default_locale_code)
        if not locale_id:
            raise MockDataPrerequisiteError(f"Locale {self._default_locale_code!r} not found or inactive. Run init-all (or init-locales) first.")

        ministry_id = await self._resolve_draft_ministry(
            ministry_name=ministry_name, steward_email=account_rows[PERSONA_STEWARD]["email"], steward_id=steward_id
        )
        room_id = await self._first_active_room_id()
        owner_position_id, owner_position_code = await self._first_owning_position()

        now = self._clock()
        personal_start = (now + timedelta(days=3)).replace(hour=10, minute=0, second=0, microsecond=0)
        personal_end = personal_start + timedelta(hours=2)
        church_start = (now + timedelta(days=5)).replace(hour=14, minute=0, second=0, microsecond=0)
        church_end = church_start + timedelta(hours=2)

        personal_booking_id = await self._insert_booking(
            user_id=personal_id,
            ministry_id=None,
            room_id=room_id,
            start_at=personal_start,
            end_at=personal_end,
            remark="Mock QA: personal Rental Booking",
            title="Personal booking",
        )

        await (
            self._session.update(OrgMinistry)
            .values(status=MinistryStatus.ACTIVE.value, is_active=True, submitted_at=now, submitted_by_id=steward_id, approved_at=now, approved_by_id=None)
            .where(OrgMinistry.id == ministry_id)
            .execute()
        )
        await (
            self._session.insert(OrgMinistryApproval)
            .values(
                id=uuid.uuid4(),
                ministry_id=ministry_id,
                owner_position_id=None,
                status=MinistryApprovalStatus.APPROVED.value,
                requested_by_id=steward_id,
                decided_at=now,
                comment=STEWARD_MINISTRY_APPROVAL_COMMENT,
            )
            .execute()
        )

        church_booking_id = await self._insert_booking(
            user_id=steward_id,
            ministry_id=ministry_id,
            room_id=room_id,
            start_at=church_start,
            end_at=church_end,
            remark="Mock QA: steward Church Activity Booking",
            title="Church activity",
        )

        await PositionRepository(self._session).assign_incumbent(position_id=owner_position_id, user_id=owner_id)

        application_id = uuid.uuid4()
        application_name = f"Mock Ministry Application {ministry_code}"
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
                    submitted_by_id=steward_id,
                    created_by_id=steward_id,
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
            .values(id=uuid.uuid4(), ministry_id=application_id, user_id=steward_id, member_role=MinistryMemberRole.PRIMARY.value)
            .execute()
        )
        await (
            self._session.insert(OrgMinistryApproval)
            .values(
                id=uuid.uuid4(),
                ministry_id=application_id,
                owner_position_id=owner_position_id,
                status=MinistryApprovalStatus.PENDING.value,
                requested_by_id=steward_id,
            )
            .execute()
        )

        await self._session.commit()
        click.echo(
            click.style(
                f"Mock data committed: personal Rental Booking, Active Ministry {ministry_name!r} with a Church Activity Booking, "
                f"Owner assigned to {owner_position_code!r}, and Ministry Application {application_name!r} pending that Owner's decision.",
                fg="green",
            )
        )

        return SeedMockDataResult(
            ministry_id=ministry_id,
            ministry_name=ministry_name,
            personal_rental_booking_id=personal_booking_id,
            church_activity_booking_id=church_booking_id,
            owner_position_id=owner_position_id,
            owner_position_code=owner_position_code,
            ministry_application_id=application_id,
            ministry_application_name=application_name,
        )
