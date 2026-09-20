# 0020. Recurring Booking conflict preview and explicit exclusions

## Status

Accepted

## Context

ADR 0019 creates a Recurring Booking Series as Pending-payment and rejects the first occupancy, Blackout, or Weekly Rental Booking quota conflict. That first-fail create is not enough for Personal Rental and Non-priority Ministry Series: the Booker must see every unavailable occurrence, then either omit those dates or revise rooms and the shared Recurring Booking time window. Silent partial creation is forbidden. The server remains authoritative on the final unexcluded set.

Priority Ministry override of Rental occupancy is a later ticket (core-api#150). This slice still rejects remaining occupancy and every Blackout at create time.

## Decision

### Preview

- Add `RecurringBookingService.preview_conflicts` on the same Recurring Booking service seam as create.
- Member `POST /api/v1/facility/booking-series/preview` and admin `POST /admin/api/v1/facility/booking-series/preview` share that method.
- The request shape matches create (minus `excluded_dates`). Preview does not persist a Series or reserve slots.
- The result lists every conflicting occurrence, distinguished by kind: occupancy, Blackout, or Weekly Rental Booking quota. Occupancy and Blackout include the affected `facility_ids`. Quota conflicts have an empty room list. Ministry Series omit quota conflicts.
- For a structurally valid weekly proposal, the same result also includes Series Estimated Total (`quoted_amount` + `currency`) for the full generated occurrence set before conflict exclusions, via `RecurringBookingService._quote_remaining_occurrences` (the quoting path Draft create/update evaluation already uses). Invalid proposals still fail as before; preview remains non-persisting.

### Exclusions on create

- Create accepts `excluded_dates`. Each date must be a generated occurrence that currently has at least one previewable conflict. Arbitrary dates (non-occurrences or currently free dates) are rejected with `FACILITY_RECURRING_INVALID_EXCLUSION`.
- The minimum unexcluded occurrence count is applied after those approved exclusions.
- Create re-evaluates occupancy, Blackout, and quota on the remaining dates in the same transaction and recalculates Series payment total from that remaining set only. A stale preview (a remaining date now conflicts) fails with the existing occupancy / Blackout / quota error codes.
- Revising rooms or the shared time window is a new preview/create proposal; it is not a separate mutation API.

## Considered options

- Persist a preview token and require it on create — rejected. Re-evaluation in the create transaction is the source of truth; a token would still go stale.
- Allow excluding any date in the generated range — rejected. That bypasses rule evaluation and would let a Booker drop free weeks to shrink a Series without a conflict.
- Auto-omit all conflicts when create is retried — rejected. Partial creation needs explicit Booker approval.

## Consequences

- ADR 0019's "reject the first conflict on create" still holds when `excluded_dates` is empty.
- Clients must call preview, then create with the dates they choose to omit, or change rooms/time and preview again.
- Priority Ministry occupancy override must not be implemented here.

## Related

- core-api#139 (spec), #148 (create), #149 (this slice), #150 (Priority Ministry override)
- ADR 0019
