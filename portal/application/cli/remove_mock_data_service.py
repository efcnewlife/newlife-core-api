"""
`remove-mock-data` orchestration: hard-delete every `@test.local` Mock user and all
QA business data it derived — Bookings, Recurring Booking Series, Booking Drafts,
Recurring Series Drafts, Ministries, steward/position relationships, and `mock:`-marked
slot templates and Blackouts — while preserving catalog data (locales, RBAC, positions, rooms, rates,
system settings, Legal Documents, ...) and CSV archives.

Never guesses: a candidate Ministry that also has a non-Mock (or, when opted in,
non-legacy) dependency blocks the whole run, with nothing deleted, rather than
silently orphaning real data (ADR 0025).
"""

from dataclasses import dataclass
from uuid import UUID

import click

from portal.application.cli.mock_fixture_plans import MOCK_RUN_MARKER_PREFIX
from portal.application.cli.mock_user_seed_service import email_has_testing_suffix, resolve_testing_account_email_suffix
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import (
    AuthUser,
    FacilityBooking,
    FacilityBookingDraft,
    FacilityBookingSeries,
    FacilityBookingSeriesDraft,
    FacilityRoomBlackout,
    FacilityRoomSlotTemplate,
    OrgMinistry,
    OrgMinistryApproval,
    OrgMinistryMember,
    OrgMinistryTranslation,
)

LEGACY_SEED_MARKER = "seed:"
LEGACY_DEMO_ACCOUNT_EMAILS = frozenset(
    {
        "seed.booker.1@local.test",
        "seed.booker.2@local.test",
        "seed.booker.3@local.test",
        "seed.booker.4@local.test",
        "seed.booker.5@local.test",
        "seed.ministry.primary@local.test",
        "seed.ministry.secondary@local.test",
        "seed.ministry.secondary2@local.test",
    }
)

# (label, model, user-holding columns to check) — every model here also carries ministry_id.
_MINISTRY_SCOPED_MODELS = (
    ("non-Mock Ministry member", OrgMinistryMember, (OrgMinistryMember.user_id,)),
    ("non-Mock Booking", FacilityBooking, (FacilityBooking.user_id,)),
    ("non-Mock Recurring Booking Series", FacilityBookingSeries, (FacilityBookingSeries.user_id,)),
    ("non-Mock Booking Draft", FacilityBookingDraft, (FacilityBookingDraft.user_id,)),
    ("non-Mock Recurring Series Draft", FacilityBookingSeriesDraft, (FacilityBookingSeriesDraft.user_id,)),
    ("non-Mock Ministry Approval decision", OrgMinistryApproval, (OrgMinistryApproval.requested_by_id, OrgMinistryApproval.resolved_by_id)),
)


class MockDataDependencyError(ValueError):
    """Raised when a candidate Mock Ministry also has a non-Mock-user dependency; nothing is deleted."""


def _as_uuid(value: object) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _unique_uuids(values) -> list[UUID]:
    return sorted({_as_uuid(v) for v in (values or [])}, key=str)


@dataclass(frozen=True)
class RemoveMockDataResult:
    removed_user_count: int
    removed_ministry_count: int
    removed_booking_count: int
    removed_series_count: int
    removed_draft_count: int
    removed_slot_template_count: int = 0
    removed_blackout_count: int = 0


class RemoveMockDataService:
    """Hard-delete Mock users, marked non-user fixtures, and optional exact legacy Demo data."""

    def __init__(self, session: Session, *, email_suffix: str | None = None):
        self._session = session
        self._email_suffix = email_suffix or resolve_testing_account_email_suffix()

    async def _user_rows(self) -> list:
        return await self._session.select(AuthUser.id, AuthUser.email).fetch() or []

    async def _scoped_user_ids(self, *, include_legacy_demo: bool) -> list[UUID]:
        # Suffix check matches other Mock lifecycle commands; exact emails are the frozen legacy identities.
        rows = await self._user_rows()
        ids = [row["id"] for row in rows if email_has_testing_suffix(row["email"], suffix=self._email_suffix)]
        if include_legacy_demo:
            ids.extend(row["id"] for row in rows if row["email"] in LEGACY_DEMO_ACCOUNT_EMAILS)
        return _unique_uuids(ids)

    async def _candidate_ministry_ids(self, user_ids: list[UUID]) -> list[UUID]:
        if not user_ids:
            return []
        rows = await self._session.select(OrgMinistryMember.ministry_id).where(OrgMinistryMember.user_id.in_(user_ids)).fetchvals()
        return _unique_uuids(rows)

    async def _seed_marked_ministry_ids(self) -> list[UUID]:
        rows = await self._session.select(OrgMinistryTranslation.ministry_id, OrgMinistryTranslation.name).fetch()
        return _unique_uuids(row["ministry_id"] for row in (rows or []) if (row["name"] or "").startswith(LEGACY_SEED_MARKER))

    async def _ministries_with_out_of_scope_dependency(self, model, *, ministry_ids: list[UUID], scoped_user_ids: list[UUID], user_columns: tuple) -> set[UUID]:
        found: set[UUID] = set()
        for user_column in user_columns:
            query = self._session.select(model.ministry_id).where(model.ministry_id.in_(ministry_ids)).where(user_column.isnot(None))
            if scoped_user_ids:
                query = query.where(user_column.notin_(scoped_user_ids))
            rows = await query.fetchvals()
            found |= set(_unique_uuids(rows))
        return found

    async def _ministry_names(self, ministry_ids: list[UUID]) -> dict[UUID, str]:
        if not ministry_ids:
            return {}
        rows = (
            await self._session.select(OrgMinistryTranslation.ministry_id, OrgMinistryTranslation.name)
            .where(OrgMinistryTranslation.ministry_id.in_(ministry_ids))
            .fetch()
        )
        names: dict[UUID, str] = {}
        for row in rows or []:
            names.setdefault(_as_uuid(row["ministry_id"]), row["name"])
        return names

    async def _dependency_error_message(self, offending: dict[str, set[UUID]]) -> str:
        all_ids = sorted({mid for ids in offending.values() for mid in ids}, key=str)
        names = await self._ministry_names(all_ids)
        parts = [f"{label} ({', '.join(names.get(mid, str(mid)) for mid in sorted(ids, key=str))})" for label, ids in offending.items()]
        return "Cannot remove Mock data: " + "; ".join(parts) + ". Resolve the non-Mock dependency manually, then re-run remove-mock-data."

    async def _out_of_scope_seed_marked_booking_owners(self, scoped_user_ids: list[UUID]) -> list[UUID]:
        rows = await self._session.select(FacilityBooking.user_id, FacilityBooking.remark).fetch()
        scoped = set(scoped_user_ids)
        owners: list[object] = []
        for row in rows or []:
            if not (row.get("remark") or "").startswith(LEGACY_SEED_MARKER):
                continue
            owner_id = _as_uuid(row["user_id"])
            if owner_id not in scoped:
                owners.append(owner_id)
        return _unique_uuids(owners)

    async def _ids_with_name_containing(self, model, marker: str) -> list[UUID]:
        rows = await self._session.select(model.id, model.name).fetch()
        return _unique_uuids(row["id"] for row in (rows or []) if marker in (row["name"] or ""))

    async def _ids_with_name_prefix(self, model, marker: str) -> list[UUID]:
        rows = await self._session.select(model.id, model.name).fetch()
        return _unique_uuids(row["id"] for row in (rows or []) if (row["name"] or "").startswith(marker))

    async def _delete_by_ids(self, model, ids: list[UUID]) -> int:
        if not ids:
            return 0
        await self._session.delete(model).where(model.id.in_(sorted(ids, key=str))).execute()
        return len(ids)

    async def _delete_ministry_scoped(self, model, *, scoped_user_ids: list[UUID], candidate_ministry_ids: list[UUID]) -> int:
        """Delete rows owned by a scoped user or attached to a candidate Ministry; return the count removed."""
        ids: set[UUID] = set()
        if scoped_user_ids:
            ids |= set(_unique_uuids(await self._session.select(model.id).where(model.user_id.in_(scoped_user_ids)).fetchvals()))
        if candidate_ministry_ids:
            ids |= set(_unique_uuids(await self._session.select(model.id).where(model.ministry_id.in_(candidate_ministry_ids)).fetchvals()))
        return await self._delete_by_ids(model, sorted(ids, key=str))

    async def run(self, *, include_legacy_demo: bool = False) -> RemoveMockDataResult:
        scoped_user_ids = await self._scoped_user_ids(include_legacy_demo=include_legacy_demo)

        marked_slot_ids = set(await self._ids_with_name_containing(FacilityRoomSlotTemplate, MOCK_RUN_MARKER_PREFIX))
        marked_blackout_ids = set(await self._ids_with_name_containing(FacilityRoomBlackout, MOCK_RUN_MARKER_PREFIX))
        if include_legacy_demo:
            marked_slot_ids |= set(await self._ids_with_name_prefix(FacilityRoomSlotTemplate, LEGACY_SEED_MARKER))
            marked_blackout_ids |= set(await self._ids_with_name_prefix(FacilityRoomBlackout, LEGACY_SEED_MARKER))
        marked_slot_ids = _unique_uuids(marked_slot_ids)
        marked_blackout_ids = _unique_uuids(marked_blackout_ids)

        candidate_ministry_ids = set(await self._candidate_ministry_ids(scoped_user_ids))
        if include_legacy_demo:
            candidate_ministry_ids |= set(await self._seed_marked_ministry_ids())
        candidate_ministry_ids = _unique_uuids(candidate_ministry_ids)

        if include_legacy_demo:
            stray_owners = await self._out_of_scope_seed_marked_booking_owners(scoped_user_ids)
            if stray_owners:
                raise MockDataDependencyError(
                    "Cannot remove Mock data: seed-marked Booking owned by a non-legacy account. "
                    "Resolve the non-Mock or non-legacy dependency manually, then re-run remove-mock-data."
                )

        if not scoped_user_ids and not marked_slot_ids and not marked_blackout_ids and not candidate_ministry_ids:
            click.echo(click.style(f"No Mock users found (suffix {self._email_suffix!r}); nothing to remove.", fg="yellow"))
            return RemoveMockDataResult(0, 0, 0, 0, 0)

        if candidate_ministry_ids:
            offending: dict[str, set[UUID]] = {}
            for label, model, user_columns in _MINISTRY_SCOPED_MODELS:
                found = await self._ministries_with_out_of_scope_dependency(
                    model, ministry_ids=candidate_ministry_ids, scoped_user_ids=scoped_user_ids, user_columns=user_columns
                )
                if found:
                    offending[label] = found
            if offending:
                raise MockDataDependencyError(await self._dependency_error_message(offending))

        booking_count = await self._delete_ministry_scoped(FacilityBooking, scoped_user_ids=scoped_user_ids, candidate_ministry_ids=candidate_ministry_ids)
        series_count = await self._delete_ministry_scoped(FacilityBookingSeries, scoped_user_ids=scoped_user_ids, candidate_ministry_ids=candidate_ministry_ids)
        draft_count = await self._delete_ministry_scoped(FacilityBookingDraft, scoped_user_ids=scoped_user_ids, candidate_ministry_ids=candidate_ministry_ids)
        draft_count += await self._delete_ministry_scoped(
            FacilityBookingSeriesDraft, scoped_user_ids=scoped_user_ids, candidate_ministry_ids=candidate_ministry_ids
        )

        if candidate_ministry_ids:
            await self._session.delete(OrgMinistry).where(OrgMinistry.id.in_(candidate_ministry_ids)).execute()

        # Profiles, tokens, roles, and steward/position (OrgPositionAssignment) relationships are
        # ondelete=CASCADE on user_id, so this one delete removes them too.
        if scoped_user_ids:
            await self._session.delete(AuthUser).where(AuthUser.id.in_(scoped_user_ids)).execute()

        slot_template_count = await self._delete_by_ids(FacilityRoomSlotTemplate, marked_slot_ids)
        blackout_count = await self._delete_by_ids(FacilityRoomBlackout, marked_blackout_ids)
        await self._session.commit()

        result = RemoveMockDataResult(
            removed_user_count=len(scoped_user_ids),
            removed_ministry_count=len(candidate_ministry_ids),
            removed_booking_count=booking_count,
            removed_series_count=series_count,
            removed_draft_count=draft_count,
            removed_slot_template_count=slot_template_count,
            removed_blackout_count=blackout_count,
        )
        summary = (
            f"Mock data removed: {result.removed_user_count} user(s), {result.removed_ministry_count} Ministry(ies), "
            f"{result.removed_booking_count} Booking(s), {result.removed_series_count} Recurring Booking Series, "
            f"{result.removed_draft_count} Booking Draft(s), {result.removed_slot_template_count} slot template(s), "
            f"{result.removed_blackout_count} Blackout(s)."
        )
        click.echo(click.style(summary, fg="green"))
        logger.info(summary)
        return result
