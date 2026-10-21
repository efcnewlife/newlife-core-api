# 0036. Reviewed, atomic Recurring Priority Ministry override

## Status

Accepted

## Context

ADR 0021 lets a Priority Ministry Recurring Series displace future Rental occurrences inside create, with no review step, and sent override mail before the request transaction committed. ADR 0035 made One-time override two-stage (side-effect-free review, then acknowledged confirmation) and added reusable support in `priority_override`. EFC-259 brings member Recurring preview, owned Series Draft review, and final Series creation under the same guarantees.

## Decision

### Review

- Member `POST /booking-series/preview` and owned Series Draft read/update return `overrideImpacts` (whole target Bookings with every released room interval; a Series target is one occurrence) and `overrideReviewToken`. Review never reserves, displaces, or notifies.
- The token is the ADR 0035 token, not a second lifecycle. Its proposal is bound to a Recurring marker, every remaining occurrence × room interval, and the explicit `excluded_dates`. Excluded occurrences contribute no impact.
- A Draft issues a token only when confirmable. Preview (which has no Title) issues one when exclusions are valid, the remaining count meets the minimum, and no remaining conflict blocks. Preview now accepts optional `excluded_dates` so the direct create path can be reviewed with the same exclusions it will send.

### Confirmation

- `POST /booking-series-drafts/{id}/confirm` takes an optional body `{override_review_token}`; member `POST /booking-series` takes `override_review_token`. With no impact, no body or token is needed.
- Under the per-room advisory locks, create re-evaluates occupancy and applies ADR 0035 rules: missing review → `FACILITY_BOOKING_OVERRIDE_REVIEW_REQUIRED`; new target, changed intervals, or different Booker/Ministry/schedule/rooms/exclusions → `FACILITY_BOOKING_OVERRIDE_REVIEW_STALE`; an unchanged subset proceeds. Lost priority or stewardship turns targets into blocking conflicts.
- One transaction commits the remaining Series, every target marked `overridden` with all slots cancelled, one override-log row per overlapping room, and Draft deletion. Only affected target occurrences are displaced, never their Series.
- Override mail is queued with `notify_displaced_bookers_after_commit` (now carrying `series_id`), so it is sent only after commit, never on preview or rollback.

### Error contexts

- Draft-confirm and Series-create conflict contexts carry `conflicts` without `occupying_bookings`, so Booker identity and Booking ids never reach member responses. Ministry conflicts keep the authorized steward contact for the Conflict popup; Personal callers see generic occupancy.

### Administrator create

- Admin Series create (`require_override_review = False`) keeps the ADR 0021 unreviewed override, now with post-commit mail. Staff already act with full visibility; requiring a member review token there is out of scope.

## Considered options

- A Recurring-specific token or stored review row — rejected: ADR 0035's stateless token already binds context and impacts; only the proposal encoding differs.
- Making admin Series create never override (mirroring One-time admin) — rejected for this slice: it removes an existing staff capability the ticket does not ask to change.

## Consequences

- Facility Booking frontend sends the reviewed `overrideReviewToken` on Draft confirm or direct Series create and refreshes the review on either review error (EFC-261).
- Clients that preview with exclusions should send the same `excluded_dates` to preview and create.

## Related

- EFC-254 (spec), EFC-258 / ADR 0035 (One-time), EFC-259 (this slice), EFC-261 (frontend)
- ADR 0021, ADR 0028 (Series Draft)
