# 0035. Reviewed, atomic One-time Priority Ministry override

## Status

Accepted

## Context

ADR 0021 lets a Priority Ministry Recurring Series displace future Rental occurrences in its create transaction. EFC-254 / EFC-258 extend priority to One-time Booking but require two-stage confirmation: Draft review shows the whole-Booking impact without side effects, and only the final confirmation displaces — and only what was reviewed. The previous One-time create rejected every occupied interval, checked occupancy outside any lock, and Recurring override mail was sent before the request transaction committed.

## Decision

### Review acknowledgement

- Owned Booking Draft read/update returns `isConfirmable`, redacted `conflicts`, `overrideImpacts` (each target Booking with all released room intervals; Series targets are one occurrence) and `overrideReviewToken` when confirmable with a non-empty impact.
- The token is stateless: an HMAC-SHA256 (key derived from `JWT_SECRET_KEY`) over a digest of Booker, Ministry, canonical room/time proposal, and a per-target fingerprint of released intervals. Identifiers are hashed; the token is opaque. No Draft column or migration is needed.
- Member `POST /bookings` accepts `override_review_token`. With a non-empty current impact: missing token → 409 `FACILITY_BOOKING_OVERRIDE_REVIEW_REQUIRED`; bad signature, different context/proposal, a new target, or a target whose released intervals changed → 409 `FACILITY_BOOKING_OVERRIDE_REVIEW_STALE`. A subset of unchanged reviewed targets proceeds. No impact → no token needed. Omitting a Draft id does not skip this check.

### Eligibility and protection

- Override requires an Active Priority Ministry whose current primary/secondary steward is the Booker, re-checked at confirmation, and a Non-ministry Booking whose start is strictly after transaction-time now (effective Pending-payment and Confirmed alike). Ministry occupancy, started Bookings, and Blackouts are never displaced. Blocking occupancy raises the existing `FACILITY_BOOKING_SCHEDULING_CONFLICT` with `context.conflicts`: Ministry occupancy shows the Ministry name and current primary steward contact; a Non-priority Ministry sees a Rental Booker's name and email; Personal callers get generic occupancy only.
- Administrator create never overrides (`allow_priority_override` is set only by the member route).

### Atomic confirmation

- Before evaluation, create takes `pg_advisory_xact_lock` per proposed room (sorted) so a competing create cannot enter between validation and writes; Recurring Series create takes the same locks.
- In one transaction: create the replacement, mark each target `overridden` with all its slots cancelled, write one `booking_override_log` row per overlapping room (ADR 0021 semantics), and delete the owned Draft. Any failure rolls all of it back.

### Post-commit notification

- `Session.add_after_commit` (exposed to services as `TransactionHooksPort`) runs callbacks only after a real commit; rollback discards them. One-time override mail is queued there. The mail service sends each displaced Booker one mail linking their own affected Booking, and the existing staff recipients (Booking Payment Confirmation Operators, Facility Deacon) one mail covering every item; `GRAPH_MAIL_OVERRIDE_TO` safeguards are unchanged. The proposal and impact fingerprints normalise datetimes to UTC so the same instant sent with a local offset is not stale. Delivery failure is logged and never undoes the commit.

## Considered options

- Persist a review row on the Draft — rejected: needs a human-run migration and adds state that must be invalidated; the signed fingerprint gives the same stale detection.
- `SELECT … FOR UPDATE` on slot rows — rejected: it cannot lock rows that do not exist yet (a new occupant inserting into a free interval).
- Sending mail inside the service after writes (ADR 0021 Recurring behavior) — rejected for One-time: mail could go out for a transaction that later rolls back. Recurring adopts the hook in EFC-259.

## Consequences

- Facility Booking frontend sends `overrideReviewToken` from the reviewed Draft as `override_review_token`, and refreshes the Draft on either review error.
- Rotating `JWT_SECRET_KEY` invalidates outstanding review tokens (members re-review).
- Recurring confirmation (EFC-259) should reuse `priority_override` (token, `apply_whole_booking_overrides`, `notify_displaced_bookers_after_commit`).

## Related

- EFC-254 / facility-booking-frontend#155 (spec), EFC-258 (this slice), EFC-259 (Recurring), EFC-260 (frontend)
- ADR 0018 (Booking Draft), ADR 0021 (Recurring override), ADR 0033, ADR 0034
