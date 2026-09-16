# 0019. Recurring Booking Series foundation and Pending-payment creation

## Status

Accepted

## Context

One-time Booking create writes a single confirmed `facility.booking` row. The unused `recurrence_rule` / `recurrence_end_at` columns do not materialize occupancy, cannot omit dates, and cannot support Church Activity priority, payment holds, or occurrence-level cancellation.

Church rental policy requires weekly Recurring Booking Series inside a fixed January-June or July-December Recurring Booking period, a configured Recurring Booking availability window after December 1 / June 1, a minimum of four unexcluded weekly Booking Occurrences, a Sunday-Saturday Weekly Rental Booking quota, facility-local wall-clock times with deterministic DST handling, and a Series payment total that stays Pending-payment until staff confirm it.

This ADR covers the Series aggregate, System Settings, and create APIs (core-api#148). Conflict preview, Priority Ministry override, payment confirmation/expiry sweep, and cancellation scopes are follow-up tickets.

## Decision

### Aggregate

- Add `facility.booking_series` as the Recurring Booking Series parent. Each Booking Occurrence is a real `facility.booking` row with `booking_type = recurring`, `series_id` pointing at the parent, its own Booking lines, and occupancy slots.
- Do **not** use a single Booking RRULE row as the source of occupancy. Existing `recurrence_rule` / `recurrence_end_at` columns stay unused by this slice.
- The Booker supplies first and last occurrence dates (same weekday, one Recurring Booking period), one Recurring Booking time window (`local_start_time` / `local_end_time`), and one or more rooms that all use that window.
- Occurrences are generated weekly from first through last inclusive. Shared-window rooms are copied onto every occurrence.

### Status and payment

- A successful Personal Rental Series (and a Ministry Series in this slice) is created as `pending_payment`. Slots are reserved with `BookingSlotStatus.CONFIRMED` so they occupy the room the same way Confirmed Bookings do.
- Store `payment_hold_expires_at` on the Series as `now + facility.pending_payment_hold_hours` (NUMBER, default 72). Manual confirmation and the expiry sweep are out of scope here.
- Recalculate the Series payment total server-side from every materialized occurrence using `BookingType.RECURRING` pricing. Persist that total on the Series and per-occurrence snapshots on each Booking.

### System Settings

Built-in `facility` settings, seeded insert-if-missing:

| Key | Type | Default | Reader |
| --- | --- | --- | --- |
| `recurring_booking_availability_window` | OBJECT `{amount, unit}` | `{amount: 4, unit: "weeks"}` | `SettingService.get_recurring_booking_availability_window()` |
| `min_recurring_booking_weeks` | NUMBER | `4` | `SettingService.get_min_recurring_booking_weeks()` |
| `pending_payment_hold_hours` | NUMBER | `72` | `SettingService.get_pending_payment_hold_hours()` |

`unit` is one of `days`, `weeks`, or calendar-relative `months`. Amount must be a positive integer. SettingService validates this shape on admin update (not a generic JSON object editor). Cache-then-DB readers match `get_max_booking_lines()`.

### Policy gates on create

- Recurring Booking period: January-June or July-December; first and last dates must share one period.
- Recurring Booking opening date: December 1 for January-June, June 1 for July-December, in the facility timezone. The availability window is `[opening, opening + duration)` in local time.
- Minimum unexcluded weekly occurrences: `facility.min_recurring_booking_weeks` (default 4). This slice has no exclusions; the generated set must meet the minimum.
- Recurring Booking local time: localize each occurrence independently. Reject a nonexistent DST wall time; an ambiguous time uses `fold=0` (earlier offset).
- Weekly Rental Booking quota: at most one Rental Booking occurrence per facility-local Sunday 00:00 through Saturday 23:59:59, including Pending-payment Rentals. Ministry Series do not count toward or consume this quota.
- Facility Booking eligible account: church-domain email (`efcnewlife.org`). Admin on-behalf create still checks the **Booker**.
- Ministry Series: Active Ministry and current primary/secondary steward (existing `is_user_booking_member`). Priority vs non-priority is recorded (`has_priority_booking` snapshot) but override of conflicting Rentals is deferred to the Priority Ministry ticket. This slice rejects occupancy/Blackout conflicts for every Series kind.

### APIs

Member `POST /api/v1/facility/booking-series` and admin `POST /admin/api/v1/facility/booking-series` share `RecurringBookingService.create_series`. Admin requires `user_id` (Booker); Operator identity remains audit `created_by_id` / `created_by`. Both return the same Series + occurrence contract.

### Human-owned migration

Agents must not add or edit `alembic/versions/**`. A human migration must create `facility.booking_series` and add nullable `facility.booking.series_id`. Suggested columns are documented on the ORM models.

## Considered options

- Reuse `recurrence_rule` on one Booking row — rejected. It does not produce occupancy slots or independent occurrences.
- Store Pending-payment only on the Series and leave occurrence status `confirmed` — rejected. Occurrence status must match payment state for My Bookings and admin detail.
- Hold slots with a new `held` slot status — rejected for this slice. Existing overlap checks already key off `BookingSlotStatus.CONFIRMED`; using it keeps occupancy consistent until the expiry ticket adds query-time logical expiry.

## Consequences

- Calendar/Grid continue to query Booking rows; materialized occurrences appear without a Series-specific range endpoint in this slice.
- Conflict preview, exclusions, Priority Ministry override, payment confirmation, expiry sweep, and cancellation scopes must not be bolted onto create without their tickets.
- Until the human migration runs, local/dev databases will not persist Series rows even though the application code is present.

## Related

- core-api#139 (spec), #148 (this slice)
- ADR 0015 (member create remains one-time; Recurring is now this ADR)
- ADR 0018 (System Setting reader pattern)
