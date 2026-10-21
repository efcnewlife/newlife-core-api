"""
One-time proposal occupancy evaluation for Draft review and final confirmation (ADR 0035).

Classifies each occupant of the proposed lines as blocking (redacted for Personal callers)
or as an eligible whole-Booking Priority Ministry override target.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from portal.application.facility.booking_line_validation import ResolvedBookingLine
from portal.application.facility.priority_override import OverrideTarget, room_interval_key
from portal.application.facility.recurring_override_mail_content import resolve_bilingual_activity_names
from portal.application.facility.results import BookingConflictResult, OverrideImpactResult, RecurringOccupyingBookingResult
from portal.domain.facility.constants import RecurringConflictKind
from portal.domain.org.constants import MinistryMemberRole, MinistryStatus
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.org.ministry_repository import MinistryRepository


@dataclass(frozen=True)
class MinistryProposalContext:
    """Current, validated Ministry association of a proposal; absent for Personal proposals."""

    ministry_id: UUID
    is_priority: bool
    name_en: str
    name_zh: str


@dataclass
class OneTimeOccupancyEvaluation:
    conflicts: list[BookingConflictResult] = field(default_factory=list)
    targets: list[OverrideTarget] = field(default_factory=list)

    @property
    def impacts(self) -> list[OverrideImpactResult]:
        return [target.impact for target in self.targets]


async def load_ministry_proposal_context(ministry_repository: MinistryRepository, ministry_id: UUID, user_id: UUID) -> Optional[MinistryProposalContext]:
    """Return the context only while the Ministry is Active and the user is its current primary/secondary steward."""
    ministry = await ministry_repository.get_by_id(ministry_id, all_locales=True)
    if ministry is None or ministry.status != MinistryStatus.ACTIVE.value:
        return None
    if not await ministry_repository.is_user_booking_member(ministry_id, user_id):
        return None
    name_en, name_zh = resolve_bilingual_activity_names(ministry.translations, ministry.name)
    return MinistryProposalContext(ministry_id=ministry_id, is_priority=bool(ministry.has_priority_booking), name_en=name_en, name_zh=name_zh)


def one_time_proposal(lines: list[ResolvedBookingLine]) -> list[str]:
    """Canonical room/time proposal the override review is bound to."""
    return [room_interval_key(line.facility_id, line.start_at, line.end_at) for line in lines]


async def _primary_steward_contact(ministry_repository: MinistryRepository, ministry_id: UUID) -> tuple[Optional[str], Optional[str]]:
    members = await ministry_repository.list_members(ministry_id)
    primary = next((member for member in members if member.member_role == MinistryMemberRole.PRIMARY.value), None)
    if primary is None:
        return None, None
    return primary.display_name or primary.email, primary.email


async def evaluate_one_time_occupancy(
    *,
    lines: list[ResolvedBookingLine],
    context: Optional[MinistryProposalContext],
    now_utc: datetime,
    local_tz: ZoneInfo,
    booking_repository: BookingRepository,
    ministry_repository: MinistryRepository,
    allow_override: bool = False,
    locale_id: Optional[UUID] = None,
) -> OneTimeOccupancyEvaluation:
    """Only an Active Priority Ministry may displace future, not-started Non-ministry Bookings; everything else blocks."""
    can_override = allow_override and context is not None and context.is_priority
    evaluation = OneTimeOccupancyEvaluation()
    target_rows: dict[UUID, RecurringOccupyingBookingResult] = {}
    overlapping_by_target: dict[UUID, list[UUID]] = {}
    steward_contacts: dict[UUID, tuple[Optional[str], Optional[str]]] = {}

    for line in lines:
        rows = await booking_repository.list_occupying_slots(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, locale_id=locale_id)
        seen_on_line: set[UUID] = set()
        blocked_on_line = False
        for row in rows:
            if row.ministry_id is None and can_override and row.start_at > now_utc:
                target_rows.setdefault(row.booking_id, row)
                overlapping = overlapping_by_target.setdefault(row.booking_id, [])
                if line.facility_id not in overlapping:
                    overlapping.append(line.facility_id)
                continue
            if context is None:
                blocked_on_line = True
                continue
            if row.booking_id in seen_on_line:
                continue
            seen_on_line.add(row.booking_id)
            if row.ministry_id is not None:
                if row.ministry_id not in steward_contacts:
                    steward_contacts[row.ministry_id] = await _primary_steward_contact(ministry_repository, row.ministry_id)
                contact_name, contact_email = steward_contacts[row.ministry_id]
                evaluation.conflicts.append(
                    BookingConflictResult(
                        facility_id=line.facility_id,
                        start_at=line.start_at,
                        end_at=line.end_at,
                        kind=RecurringConflictKind.MINISTRY.value,
                        ministry_name=row.ministry_name,
                        contact_display_name=contact_name,
                        contact_email=contact_email,
                    )
                )
            else:
                show_booker = not context.is_priority
                evaluation.conflicts.append(
                    BookingConflictResult(
                        facility_id=line.facility_id,
                        start_at=line.start_at,
                        end_at=line.end_at,
                        kind=RecurringConflictKind.OCCUPANCY.value,
                        contact_display_name=row.booker_display_name if show_booker else None,
                        contact_email=row.booker_email if show_booker else None,
                    )
                )
        if blocked_on_line:
            evaluation.conflicts.append(
                BookingConflictResult(facility_id=line.facility_id, start_at=line.start_at, end_at=line.end_at, kind=RecurringConflictKind.OCCUPANCY.value)
            )

    released = await booking_repository.list_live_slot_intervals(list(target_rows)) if target_rows else {}
    for booking_id, row in target_rows.items():
        evaluation.targets.append(
            OverrideTarget(
                impact=OverrideImpactResult(
                    booking_id=booking_id,
                    is_series_occurrence=row.series_id is not None,
                    start_at=row.start_at,
                    end_at=row.end_at,
                    released_intervals=released.get(booking_id, []),
                ),
                booker_id=row.user_id,
                occurrence_date=row.start_at.astimezone(local_tz).date(),
                overlapping_facility_ids=overlapping_by_target[booking_id],
            )
        )
    return evaluation
