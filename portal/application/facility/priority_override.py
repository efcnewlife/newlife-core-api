"""
Reusable Priority Ministry override support (ADR 0035).

Reviewed-impact acknowledgement tokens, whole-Booking displacement with audit rows,
and post-commit displaced-Booker notification. Shared by One-time and Recurring confirmation.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Optional, Protocol
from uuid import UUID, uuid4

from portal.application.facility.results import OverrideImpactResult, RecurringOverrideNotification, RecurringOverrideNotificationItem
from portal.config import settings
from portal.domain.common.ports import TransactionHooksPort
from portal.domain.facility.constants import BookingErrorCode, OverrideOutcome
from portal.exceptions.responses import ConflictErrorException
from portal.infrastructure.persistence.repositories.facility.booking_repository import BookingRepository
from portal.infrastructure.persistence.repositories.facility.override_log_repository import OverrideLogRepository
from portal.libs.logger import logger

PRIORITY_OVERRIDE_REASON = "Priority Ministry override"
_TOKEN_VERSION = 1


class OverrideNotifierPort(Protocol):
    """Send Priority Ministry override notifications after the override commits."""

    async def notify_priority_override(self, notification: RecurringOverrideNotification) -> None: ...


class NullOverrideNotifier:
    """No-op notifier used when mail is not wired."""

    async def notify_priority_override(self, notification: RecurringOverrideNotification) -> None:
        return None


def override_review_secret() -> bytes:
    """Key for review tokens, derived so it is never interchangeable with a JWT signature."""
    return hmac.new(settings.JWT_SECRET_KEY.encode(), b"facility-override-review", hashlib.sha256).digest()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _context_digest(booker_id: UUID, ministry_id: Optional[UUID], proposal: list[str]) -> str:
    return _digest("\n".join([str(booker_id), str(ministry_id or ""), *sorted(proposal)]))


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def room_interval_key(facility_id: UUID, start_at: datetime, end_at: datetime) -> str:
    """Offset-independent identity of one room interval, so the same instant always hashes alike."""
    return f"{facility_id}|{_utc(start_at)}|{_utc(end_at)}"


def _impact_fingerprint(impact: OverrideImpactResult) -> str:
    intervals = sorted(room_interval_key(item.facility_id, item.start_at, item.end_at) for item in impact.released_intervals)
    return _digest("\n".join([str(impact.booking_id), _utc(impact.start_at), _utc(impact.end_at), *intervals]))


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_override_review_token(
    *, booker_id: UUID, ministry_id: Optional[UUID], proposal: list[str], impacts: list[OverrideImpactResult], secret: bytes
) -> str:
    """Sign the reviewed displacement impact for one Booker, Ministry context, and proposal; grants no reservation by itself."""
    payload = {
        "v": _TOKEN_VERSION,
        "c": _context_digest(booker_id, ministry_id, proposal),
        "t": {_digest(str(impact.booking_id)): _impact_fingerprint(impact) for impact in impacts},
    }
    body = _b64encode(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
    signature = _b64encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    return f"{body}.{signature}"


def _reviewed_fingerprints(token: str, secret: bytes, context_digest: str) -> Optional[dict[str, str]]:
    body, _, signature = token.partition(".")
    if not body or not signature:
        return None
    expected = _b64encode(hmac.new(secret, body.encode(), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, signature):
        return None
    try:
        payload = json.loads(_b64decode(body))
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("v") != _TOKEN_VERSION or payload.get("c") != context_digest:
        return None
    reviewed = payload.get("t")
    return reviewed if isinstance(reviewed, dict) else None


def require_reviewed_override(
    *, token: Optional[str], booker_id: UUID, ministry_id: Optional[UUID], proposal: list[str], impacts: list[OverrideImpactResult], secret: bytes
) -> None:
    """Allow displacement only of reviewed, unchanged targets; a subset of the reviewed impact may proceed."""
    if not impacts:
        return
    if not token:
        raise ConflictErrorException(
            detail="Priority override impact must be reviewed before confirmation", error_code=BookingErrorCode.OVERRIDE_REVIEW_REQUIRED.value
        )
    reviewed = _reviewed_fingerprints(token, secret, _context_digest(booker_id, ministry_id, proposal))
    if reviewed is None or any(reviewed.get(_digest(str(impact.booking_id))) != _impact_fingerprint(impact) for impact in impacts):
        raise ConflictErrorException(
            detail="Priority override impact changed since review; review it again", error_code=BookingErrorCode.OVERRIDE_REVIEW_STALE.value
        )


@dataclass(frozen=True)
class OverrideTarget:
    """One displaced Rental Booking (or Series occurrence) as evaluated for a proposal."""

    impact: OverrideImpactResult
    booker_id: UUID
    occurrence_date: date
    overlapping_facility_ids: list[UUID] = field(default_factory=list)


async def apply_whole_booking_overrides(
    *, booking_repository: BookingRepository, override_log_repository: OverrideLogRepository, replacements: list[tuple[UUID, OverrideTarget]], operator_id: UUID
) -> list[RecurringOverrideNotificationItem]:
    """Mark each target Booking overridden (releasing all its room intervals) and write one audit row per overlapping room.

    ``replacements`` pairs the new replacement Booking id with the target it displaces.
    """
    log_rows: list[dict] = []
    items: list[RecurringOverrideNotificationItem] = []
    overridden_ids: set[UUID] = set()
    for replacement_booking_id, target in replacements:
        booking_id = target.impact.booking_id
        if booking_id not in overridden_ids:
            await booking_repository.override_booking(booking_id, operator_id, PRIORITY_OVERRIDE_REASON)
            overridden_ids.add(booking_id)
            items.append(
                RecurringOverrideNotificationItem(
                    booking_id=booking_id,
                    booker_id=target.booker_id,
                    occurrence_date=target.occurrence_date,
                    facility_ids=list(dict.fromkeys(item.facility_id for item in target.impact.released_intervals)),
                    church_activity_booking_id=replacement_booking_id,
                )
            )
        for facility_id in target.overlapping_facility_ids:
            log_rows.append(
                dict(
                    id=uuid4(),
                    facility_booking_id=replacement_booking_id,
                    overridden_booking_id=booking_id,
                    overridden_by_id=operator_id,
                    facility_id=facility_id,
                    outcome=OverrideOutcome.OVERRIDE_APPLIED.value,
                    reason=PRIORITY_OVERRIDE_REASON,
                )
            )
    if log_rows:
        await override_log_repository.insert_logs(log_rows)
    return items


def notify_displaced_bookers_after_commit(
    *,
    transaction_hooks: TransactionHooksPort,
    notifier: OverrideNotifierPort,
    items: list[RecurringOverrideNotificationItem],
    ministry_id: UUID,
    church_activity_name: str,
    church_activity_name_zh: str,
    actor_id: UUID,
) -> None:
    """Queue the override notification until commit; nothing is sent on rollback and delivery failure never undoes the commit."""
    if not items:
        return
    notification = RecurringOverrideNotification(
        ministry_id=ministry_id, church_activity_name=church_activity_name, church_activity_name_zh=church_activity_name_zh, actor_id=actor_id, items=items
    )

    async def _send() -> None:
        await notifier.notify_priority_override(notification)

    transaction_hooks.after_commit(_send)
