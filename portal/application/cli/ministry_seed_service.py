"""
Demo ministry seed use case for CLI.

Replaces ministries whose localized names start with the demo prefix and inserts
Active ministries with a simulated Ministry Approval. This does not run the live
submit / approve workflow.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import click

from portal.application.org.ministry_schedule import encode_schedule_days_mask
from portal.cli.datas.ministry_seed_data import SEED_LOCALE_CODES, SEED_NAME_PREFIX
from portal.domain.org.constants import MinistryApprovalStatus, MinistryMemberRole, MinistryStatus
from portal.libs.consts.enums import Gender
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import (
    AuthUser,
    AuthUserProfile,
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistrySchedule,
    OrgMinistryTargetAudience,
    OrgMinistryTranslation,
    OrgMinistryType,
    OrgPosition,
    OrgTargetAudience,
    SystemLocale,
)

# Offset so submitted_at reads earlier than approved_at on demo detail views.
SUBMITTED_BEFORE_APPROVED = timedelta(days=7)
APPROVAL_COMMENT = "Simulated approval from seed-ministries"


def assert_seed_prerequisites(
    rows: list[dict[str, Any]], *, locale_codes: set[str], ministry_type_codes: set[str], target_audience_codes: set[str], owning_position_count: int
) -> None:
    """Raise a message naming the prerequisite seed command when a catalog is missing."""
    missing_locales = sorted({code for row in rows for code in row["translations"]} - locale_codes)
    if missing_locales:
        raise ValueError(f"Locale(s) {', '.join(missing_locales)} not found. Run init-locales first.")

    missing_types = sorted({row["ministry_type_code"] for row in rows} - ministry_type_codes)
    if missing_types:
        raise ValueError(f"Ministry type code(s) {', '.join(missing_types)} not found. Run seed-ministry-types first.")

    missing_audiences = sorted({code for row in rows for code in row["target_audience_codes"]} - target_audience_codes)
    if missing_audiences:
        raise ValueError(f"Target audience code(s) {', '.join(missing_audiences)} not found. Run seed-target-audiences first.")

    if owning_position_count <= 0:
        raise ValueError("No active position with can_own_ministry found. Run seed-positions first.")


def _as_uuid(value: Any) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _normalize_locale_code(locale_code: str) -> str:
    return locale_code.strip().replace("_", "-").lower()


def _locale_variants(locale_row: dict[str, Any]) -> set[str]:
    language_code = (locale_row.get("language_code") or "").strip()
    script_code = (locale_row.get("script_code") or "").strip()
    region_code = (locale_row.get("region_code") or "").strip()
    variants: set[str] = set()
    if language_code:
        variants.add(_normalize_locale_code(language_code))
    if language_code and region_code:
        variants.add(_normalize_locale_code(f"{language_code}-{region_code}"))
    if language_code and script_code and region_code:
        variants.add(_normalize_locale_code(f"{language_code}-{script_code}-{region_code}"))
    return variants


async def _load_locale_ids(session: Session) -> dict[str, UUID]:
    """Map each seed locale code to an active SystemLocale id."""
    locale_rows = await (
        session.select(SystemLocale.id, SystemLocale.language_code, SystemLocale.region_code, SystemLocale.script_code)
        .where(SystemLocale.is_active == True)
        .where(SystemLocale.is_deleted == False)
        .fetch()
    )
    resolved: dict[str, UUID] = {}
    for locale_code in SEED_LOCALE_CODES:
        normalized = _normalize_locale_code(locale_code)
        for locale_row in locale_rows or []:
            if normalized in _locale_variants(locale_row):
                resolved[locale_code] = _as_uuid(locale_row["id"])
                break
    return resolved


async def _load_catalog_ids_by_code(session: Session, catalog_model: type) -> dict[str, UUID]:
    rows = await session.select(catalog_model.id, catalog_model.code).where(catalog_model.is_active == True).fetch()
    return {str(row["code"]): _as_uuid(row["id"]) for row in rows or []}


async def _load_owning_position_ids(session: Session) -> list[UUID]:
    """Active positions whose office may own a ministry, in display order."""
    position_ids = await (
        session.select(OrgPosition.id)
        .where(OrgPosition.can_own_ministry == True)
        .where(OrgPosition.is_active == True)
        .where(OrgPosition.is_deleted == False)
        .order_by(OrgPosition.sequence)
        .fetchvals()
    )
    return [_as_uuid(position_id) for position_id in position_ids or []]


async def _ensure_demo_user(session: Session, row: dict[str, Any]) -> UUID:
    """Return the demo steward user id, creating a non-admin account when missing."""
    email = (row["email"] or "").strip().lower()
    first_name = row["first_name"]
    last_name = row["last_name"]
    # Ministry member lists display preferred_name and fall back to the email.
    preferred_name = f"{first_name} {last_name}"

    existing_id = await session.select(AuthUser.id).where(AuthUser.email == email).fetchval()
    if existing_id:
        # The email is unique, so a soft-deleted or deactivated demo user cannot be
        # re-created. Restore the flags the seeded ministries rely on instead.
        user_id = _as_uuid(existing_id)
        await session.update(AuthUser).values(is_active=True, verified=True, is_deleted=False).where(AuthUser.id == user_id).execute()
    else:
        user_id = uuid.uuid4()
        await (
            session.insert(AuthUser)
            .values(id=user_id, email=email, password_hash=None, verified=True, is_active=True, is_superuser=False, is_admin=False)
            .execute()
        )
        click.echo(f"Created demo ministry user: {email}")

    await (
        session.insert(AuthUserProfile)
        .values(id=uuid.uuid4(), user_id=user_id, first_name=first_name, last_name=last_name, preferred_name=preferred_name, gender=Gender.UNKNOWN.value)
        .on_conflict_do_update(index_elements=["user_id"], set_=dict(first_name=first_name, last_name=last_name, preferred_name=preferred_name))
        .execute()
    )
    return user_id


async def _clear_seed_ministries(session: Session) -> int:
    """Hard-delete only ministries with a demo-prefixed translation name."""
    ministry_ids = await session.select(OrgMinistryTranslation.ministry_id).where(OrgMinistryTranslation.name.like(f"{SEED_NAME_PREFIX}%")).fetchvals()
    unique_ids = sorted({_as_uuid(ministry_id) for ministry_id in ministry_ids or []})
    if not unique_ids:
        return 0
    await session.delete(OrgMinistry).where(OrgMinistry.id.in_(unique_ids)).execute()
    return len(unique_ids)


async def _insert_ministry(
    session: Session,
    row: dict[str, Any],
    *,
    locale_ids: dict[str, UUID],
    ministry_type_ids: dict[str, UUID],
    target_audience_ids: dict[str, UUID],
    owner_position_id: UUID,
    primary_user_id: UUID,
    secondary_user_id: UUID,
    submitted_at: datetime,
    approved_at: datetime,
) -> None:
    ministry_id = uuid.uuid4()
    await (
        session.insert(OrgMinistry)
        .values(
            id=ministry_id,
            ministry_type_id=ministry_type_ids[row["ministry_type_code"]],
            owner_position_id=owner_position_id,
            status=MinistryStatus.ACTIVE.value,
            is_active=True,
            has_priority_booking=row["has_priority_booking"],
            submitted_at=submitted_at,
            submitted_by_id=primary_user_id,
            approved_at=approved_at,
            approved_by_id=secondary_user_id,
            created_by_id=primary_user_id,
        )
        .execute()
    )

    for locale_code, translation in row["translations"].items():
        await (
            session.insert(OrgMinistryTranslation)
            .values(
                id=uuid.uuid4(),
                ministry_id=ministry_id,
                locale_id=locale_ids[locale_code],
                name=translation["name"],
                schedule_note=translation.get("schedule_note"),
            )
            .execute()
        )

    for member_role, user_id in ((MinistryMemberRole.PRIMARY, primary_user_id), (MinistryMemberRole.SECONDARY, secondary_user_id)):
        await session.insert(OrgMinistryMember).values(id=uuid.uuid4(), ministry_id=ministry_id, user_id=user_id, member_role=member_role.value).execute()

    for index, schedule in enumerate(row["schedules"]):
        await (
            session.insert(OrgMinistrySchedule)
            .values(
                id=uuid.uuid4(),
                ministry_id=ministry_id,
                days_of_week_mask=encode_schedule_days_mask(schedule["days_of_week"]),
                start_time=schedule["start_time"],
                end_time=schedule["end_time"],
                effective_from=schedule["effective_from"],
                effective_to=schedule["effective_to"],
                sequence=float(index),
            )
            .execute()
        )

    for audience_code in row["target_audience_codes"]:
        await (
            session.insert(OrgMinistryTargetAudience)
            .values(id=uuid.uuid4(), ministry_id=ministry_id, target_audience_id=target_audience_ids[audience_code])
            .execute()
        )

    await (
        session.insert(OrgMinistryApproval)
        .values(
            id=uuid.uuid4(),
            ministry_id=ministry_id,
            owner_position_id=owner_position_id,
            status=MinistryApprovalStatus.APPROVED.value,
            requested_by_id=primary_user_id,
            resolved_by_id=secondary_user_id,
            decided_at=approved_at,
            comment=APPROVAL_COMMENT,
        )
        .execute()
    )


async def run_ministry_seed(session: Session, rows: list[dict[str, Any]], *, demo_user_rows: list[dict[str, Any]]) -> None:
    """Replace demo ministries and insert Active ministries with a simulated approval."""
    locale_ids = await _load_locale_ids(session)
    ministry_type_ids = await _load_catalog_ids_by_code(session, OrgMinistryType)
    target_audience_ids = await _load_catalog_ids_by_code(session, OrgTargetAudience)
    owning_position_ids = await _load_owning_position_ids(session)

    assert_seed_prerequisites(
        rows,
        locale_codes=set(locale_ids),
        ministry_type_codes=set(ministry_type_ids),
        target_audience_codes=set(target_audience_ids),
        owning_position_count=len(owning_position_ids),
    )

    primary_user_id = await _ensure_demo_user(session, demo_user_rows[0])
    secondary_user_id = await _ensure_demo_user(session, demo_user_rows[1])

    deleted = await _clear_seed_ministries(session)

    approved_at = datetime.now(tz=timezone.utc)
    submitted_at = approved_at - SUBMITTED_BEFORE_APPROVED

    for index, row in enumerate(rows):
        await _insert_ministry(
            session,
            row,
            locale_ids=locale_ids,
            ministry_type_ids=ministry_type_ids,
            target_audience_ids=target_audience_ids,
            owner_position_id=owning_position_ids[index % len(owning_position_ids)],
            primary_user_id=primary_user_id,
            secondary_user_id=secondary_user_id,
            submitted_at=submitted_at,
            approved_at=approved_at,
        )

    await session.commit()
    summary = f"Ministry seed done: {len(rows)} ministry(ies) inserted, {deleted} demo ministry(ies) replaced"
    click.echo(click.style(summary, fg="green"))
    logger.info(summary)
