# 0024. Blackout impact preview and occurrence cancellation

## Status

Accepted

## Context

ADR 0019/0020 reject Recurring Booking create and conflict preview that overlap a Blackout. ADR 0023 cancels Series occurrences by scope. Staff can still persist a new Blackout that overlaps future live occurrences, leaving confirmed or pending-payment occupancy inside a closed room.

Spec #139 and core-api#153 require an impact preview before any cancellation, then operator confirmation that cancels only those future occurrences. Blackouts remain non-overridable. Refund handling stays deferred.

## Decision

### Preview

- Admin `POST /admin/api/v1/facility/room-blackouts/impact` accepts the same Blackout write body as create and does not persist a Blackout or cancel occupancy.
- `RoomBlackoutService.preview_blackout_impact` validates the proposed Blackout, then `RecurringBookingService.preview_blackout_impact` lists live future Booking Occurrences (`pending_payment` or `confirmed`, `start_at` after now) whose room intervals overlap the proposed Blackout.
- The result names each affected occurrence, its Series, rooms, and whether it is a Ministry Series (`ministry_id`) or Personal Rental (`ministry_id` is null). An empty list means confirmation is not required.

### Confirm and create

- Admin `POST /admin/api/v1/facility/room-blackouts` still creates the Blackout. When the current impact set is non-empty, `confirm_occurrence_ids` must equal that set. Missing ids are `FACILITY_BLACKOUT_IMPACT_CONFIRMATION_REQUIRED`. Stale or partial ids are `FACILITY_BLACKOUT_IMPACT_MISMATCH`. No Blackout is inserted until the sets match.
- After insert, `RecurringBookingService.apply_blackout_impact` cancels only the confirmed impacted future occurrences and records `cancelled_by_id` / `cancel_reason`. That booking cancel row is the administrative record; this slice does not write `facility.booking_override_log`. The Series is marked cancelled when no live occurrences remain (ADR 0023).
- Historical, cancelled, and overridden occurrences are not rewritten. An inactive Blackout has no impact.

### Non-overridable Blackout

- Recurring create and conflict preview keep rejecting Blackout overlap (`FACILITY_BOOKING_ROOM_BLACKOUT`). A Priority Ministry Series still cannot override a Blackout.

## Considered options

- Persist the Blackout first, then preview — rejected. CONTEXT forbids leaving an active Booking inside a Blackout.
- Let the operator confirm a subset of the impact set — rejected. Remaining overlapping occurrences would stay inside the closure.
- Re-query impact inside apply — rejected. Confirmation already named the exact ids; apply cancels those items.
- Cancel one-time Bookings in this slice — deferred. #153 is scoped to Recurring Booking Occurrences.

## Consequences

- Existing no-impact Blackout create stays a single POST. Impacting creates become preview then create with `confirm_occurrence_ids`.
- No Alembic revision is part of this ticket.

## Related

- core-api#139 (spec), #152 / ADR 0023 (Series cancellation), #153 (this slice)
- ADR 0019, ADR 0020, ADR 0021
