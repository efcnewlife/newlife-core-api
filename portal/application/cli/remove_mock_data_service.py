"""
`remove-mock-data` orchestration: hard-delete every `@test.local` Mock user and all
QA business data it derived — Bookings, Recurring Booking Series, Booking Drafts,
Ministries, and steward/position relationships — while preserving catalog data
(locales, RBAC, positions, rooms, rates, system settings, Legal Documents, ...).

Never guesses: a candidate Ministry (one with at least one Mock member) that also
has a non-Mock-user dependency blocks the whole run, with nothing deleted, rather
than silently orphaning real data (ADR 0025).
"""

from dataclasses import dataclass
from uuid import UUID

import click

from portal.application.cli.mock_user_seed_service import resolve_testing_account_email_suffix
from portal.libs.database import Session
from portal.libs.logger import logger
from portal.models import AuthUser, FacilityBooking, FacilityBookingDraft, FacilityBookingSeries, OrgMinistry, OrgMinistryMember, OrgMinistryTranslation

# (label, model) — every model here carries user_id and ministry_id columns.
_MINISTRY_SCOPED_MODELS = (
    ("non-Mock Ministry member", OrgMinistryMember),
    ("non-Mock Booking", FacilityBooking),
    ("non-Mock Recurring Booking Series", FacilityBookingSeries),
    ("non-Mock Booking Draft", FacilityBookingDraft),
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


class RemoveMockDataService:
    """Hard-delete every Mock user and its derived data; catalog data is never touched."""

    def __init__(self, session: Session, *, email_suffix: str | None = None):
        self._session = session
        self._email_suffix = email_suffix or resolve_testing_account_email_suffix()

    async def _mock_user_ids(self) -> list[UUID]:
        rows = await self._session.select(AuthUser.id).where(AuthUser.email.like(f"%{self._email_suffix}")).fetchvals()
        return _unique_uuids(rows)

    async def _candidate_ministry_ids(self, mock_user_ids: list[UUID]) -> list[UUID]:
        rows = await self._session.select(OrgMinistryMember.ministry_id).where(OrgMinistryMember.user_id.in_(mock_user_ids)).fetchvals()
        return _unique_uuids(rows)

    async def _ministries_with_non_mock_dependency(self, model, *, ministry_ids: list[UUID], mock_user_ids: list[UUID]) -> set[UUID]:
        rows = await self._session.select(model.ministry_id).where(model.ministry_id.in_(ministry_ids)).where(model.user_id.notin_(mock_user_ids)).fetchvals()
        return set(_unique_uuids(rows))

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

    async def _delete_ministry_scoped(self, model, *, mock_user_ids: list[UUID], candidate_ministry_ids: list[UUID]) -> int:
        """Delete rows owned by a Mock user or attached to a candidate Ministry; return the count removed."""
        ids = set(_unique_uuids(await self._session.select(model.id).where(model.user_id.in_(mock_user_ids)).fetchvals()))
        if candidate_ministry_ids:
            ids |= set(_unique_uuids(await self._session.select(model.id).where(model.ministry_id.in_(candidate_ministry_ids)).fetchvals()))
        if not ids:
            return 0
        await self._session.delete(model).where(model.id.in_(sorted(ids, key=str))).execute()
        return len(ids)

    async def run(self) -> RemoveMockDataResult:
        mock_user_ids = await self._mock_user_ids()
        if not mock_user_ids:
            click.echo(click.style(f"No Mock users found (suffix {self._email_suffix!r}); nothing to remove.", fg="yellow"))
            return RemoveMockDataResult(0, 0, 0, 0, 0)

        candidate_ministry_ids = await self._candidate_ministry_ids(mock_user_ids)

        if candidate_ministry_ids:
            offending: dict[str, set[UUID]] = {}
            for label, model in _MINISTRY_SCOPED_MODELS:
                found = await self._ministries_with_non_mock_dependency(model, ministry_ids=candidate_ministry_ids, mock_user_ids=mock_user_ids)
                if found:
                    offending[label] = found
            if offending:
                raise MockDataDependencyError(await self._dependency_error_message(offending))

        booking_count = await self._delete_ministry_scoped(FacilityBooking, mock_user_ids=mock_user_ids, candidate_ministry_ids=candidate_ministry_ids)
        series_count = await self._delete_ministry_scoped(FacilityBookingSeries, mock_user_ids=mock_user_ids, candidate_ministry_ids=candidate_ministry_ids)
        draft_count = await self._delete_ministry_scoped(FacilityBookingDraft, mock_user_ids=mock_user_ids, candidate_ministry_ids=candidate_ministry_ids)

        if candidate_ministry_ids:
            await self._session.delete(OrgMinistry).where(OrgMinistry.id.in_(candidate_ministry_ids)).execute()

        await self._session.delete(AuthUser).where(AuthUser.id.in_(mock_user_ids)).execute()
        await self._session.commit()

        result = RemoveMockDataResult(
            removed_user_count=len(mock_user_ids),
            removed_ministry_count=len(candidate_ministry_ids),
            removed_booking_count=booking_count,
            removed_series_count=series_count,
            removed_draft_count=draft_count,
        )
        summary = (
            f"Mock data removed: {result.removed_user_count} user(s), {result.removed_ministry_count} Ministry(ies), "
            f"{result.removed_booking_count} Booking(s), {result.removed_series_count} Recurring Booking Series, "
            f"{result.removed_draft_count} Booking Draft(s)."
        )
        click.echo(click.style(summary, fg="green"))
        logger.info(summary)
        return result
