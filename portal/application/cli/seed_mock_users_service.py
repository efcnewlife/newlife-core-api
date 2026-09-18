"""
`seed-mock-users` orchestration: random Mock users + a steward Ministry
relationship, archived as an account/Ministry CSV inventory pair (ADR 0025).
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, Protocol
from uuid import UUID

import click
from asyncpg import NotNullViolationError

from portal.application.cli.mock_account_archive import (
    ACCOUNT_CSV_COLUMNS,
    MINISTRY_CSV_COLUMNS,
    MockSeedArchiveCollisionError,
    compute_archive_filenames,
    remove_previous_archive_pair,
    write_csv,
)
from portal.application.cli.mock_locale_lookup import resolve_default_locale_id
from portal.application.cli.mock_user_persona import (
    PERSONA_STEWARD,
    MockUserPersona,
    default_random_token,
    generate_mock_ministry_code,
    generate_mock_user_personas,
)
from portal.application.cli.mock_user_seed_service import MockUserSeedService, resolve_testing_account_email_suffix
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.libs.database import Session
from portal.models import OrgMinistry, OrgMinistryMember, OrgMinistryTranslation

MINISTRY_TYPE_SCHEMA_ERROR = (
    "Ministry Type is required (NOT NULL) by this database. seed-mock-users needs the optional-Ministry-Type "
    "schema revision (migration 66fd53b703c7) applied before it can create a Ministry without a Ministry Type."
)


class ArchiveWriter(Protocol):
    """Port for the SharePoint (or fake) archive collaborator."""

    async def upload_csv_pair(self, *, env: str, account_csv: Path, ministry_csv: Path) -> Any: ...


Clock = Callable[[], datetime]


class MockSeedCatalogPrerequisiteError(ValueError):
    """Raised when a catalog prerequisite (e.g. an active default locale) is absent."""


class MockSeedArchiveUploadError(Exception):
    """Raised when the archive writer fails; the local CSV pair and DB commit are kept."""

    def __init__(self, *, account_csv: Path, ministry_csv: Path, reason: str):
        super().__init__(f"SharePoint archive upload failed. Local CSV pair retained: {account_csv}, {ministry_csv}")
        self.account_csv = account_csv
        self.ministry_csv = ministry_csv
        self.reason = reason


@dataclass(frozen=True)
class SeedMockUsersResult:
    personas: list[MockUserPersona]
    ministry_code: str
    ministry_name: str
    account_csv: Path
    ministry_csv: Path


def _account_csv_row(persona: MockUserPersona) -> dict[str, Any]:
    return {
        "email": persona.email,
        "first_name": persona.first_name,
        "last_name": persona.last_name,
        "persona": persona.persona,
        "purpose": persona.purpose,
        "is_active": persona.is_active,
        "created_in_run": True,
    }


def _ministry_csv_row(*, ministry_code: str, ministry_name: str, primary_steward_email: str) -> dict[str, Any]:
    return {
        "ministry_code": ministry_code,
        "ministry_name": ministry_name,
        "status": MinistryStatus.DRAFT.value,
        "primary_steward_email": primary_steward_email,
        "secondary_steward_emails": "",
        "purpose": "Ministry steward relationship QA scenario",
        "created_in_run": True,
    }


class SeedMockUsersService:
    """Create random personal/steward/owner/inactive Mock users and a steward Ministry, then archive the inventory."""

    def __init__(
        self,
        session: Session,
        archive_writer: ArchiveWriter,
        *,
        env: str,
        default_locale_code: str,
        output_dir: Path,
        email_suffix: Optional[str] = None,
        random_token: Callable[[], str] = default_random_token,
        clock: Clock = datetime.now,
    ):
        self._session = session
        self._archive_writer = archive_writer
        self._env = env
        self._default_locale_code = default_locale_code
        self._output_dir = output_dir
        self._email_suffix = email_suffix or resolve_testing_account_email_suffix()
        self._random_token = random_token
        self._clock = clock

    async def _insert_ministry(self, *, locale_id: UUID, ministry_name: str, steward_user_id: UUID) -> None:
        ministry_id = uuid.uuid4()
        try:
            await (
                self._session.insert(OrgMinistry)
                .values(
                    id=ministry_id,
                    ministry_type_id=None,
                    owner_position_id=None,
                    status=MinistryStatus.DRAFT.value,
                    is_active=True,
                    has_priority_booking=False,
                    created_by_id=steward_user_id,
                )
                .execute()
            )
        except NotNullViolationError as exc:
            raise RuntimeError(MINISTRY_TYPE_SCHEMA_ERROR) from exc

        await self._session.insert(OrgMinistryTranslation).values(id=uuid.uuid4(), ministry_id=ministry_id, locale_id=locale_id, name=ministry_name).execute()
        await (
            self._session.insert(OrgMinistryMember)
            .values(id=uuid.uuid4(), ministry_id=ministry_id, user_id=steward_user_id, member_role=MinistryMemberRole.PRIMARY.value)
            .execute()
        )

    async def run(self) -> SeedMockUsersResult:
        locale_id = await resolve_default_locale_id(self._session, self._default_locale_code)
        if not locale_id:
            raise MockSeedCatalogPrerequisiteError(f"Locale {self._default_locale_code!r} not found or inactive. Run init-all (or init-locales) first.")

        personas = generate_mock_user_personas(email_suffix=self._email_suffix, random_token=self._random_token)

        user_ids_by_persona: dict[str, UUID] = {}
        for persona in personas:
            user_row = await MockUserSeedService(self._session).run(
                email=persona.email, first_name=persona.first_name, last_name=persona.last_name, is_active=persona.is_active, commit=False
            )
            user_ids_by_persona[persona.persona] = user_row["id"]

        ministry_code = generate_mock_ministry_code(random_token=self._random_token)
        ministry_name = f"Mock Ministry {ministry_code}"
        steward_email = next(p.email for p in personas if p.persona == PERSONA_STEWARD)

        await self._insert_ministry(locale_id=locale_id, ministry_name=ministry_name, steward_user_id=user_ids_by_persona[PERSONA_STEWARD])

        await self._session.commit()
        click.echo(click.style(f"Mock data committed: {len(personas)} user(s), 1 Ministry ({ministry_code}).", fg="green"))

        moment = self._clock()
        filenames = compute_archive_filenames(moment, self._env)
        account_path = self._output_dir / filenames.account_filename
        ministry_path = self._output_dir / filenames.ministry_filename

        if account_path.exists() or ministry_path.exists():
            raise MockSeedArchiveCollisionError(f"Archive filename collision for this minute: {filenames.account_filename}. Retry after the next minute.")

        account_rows = [_account_csv_row(persona) for persona in personas]
        ministry_rows = [_ministry_csv_row(ministry_code=ministry_code, ministry_name=ministry_name, primary_steward_email=steward_email)]

        write_csv(account_path, ACCOUNT_CSV_COLUMNS, account_rows)
        write_csv(ministry_path, MINISTRY_CSV_COLUMNS, ministry_rows)
        remove_previous_archive_pair(self._output_dir, env=self._env, keep=(account_path, ministry_path))
        click.echo(click.style(f"Local CSV pair written: {account_path}, {ministry_path}", fg="green"))

        try:
            await self._archive_writer.upload_csv_pair(env=self._env, account_csv=account_path, ministry_csv=ministry_path)
        except Exception as exc:
            raise MockSeedArchiveUploadError(account_csv=account_path, ministry_csv=ministry_path, reason=str(exc)) from exc

        click.echo(click.style("SharePoint archive upload succeeded.", fg="green"))
        return SeedMockUsersResult(
            personas=personas, ministry_code=ministry_code, ministry_name=ministry_name, account_csv=account_path, ministry_csv=ministry_path
        )
