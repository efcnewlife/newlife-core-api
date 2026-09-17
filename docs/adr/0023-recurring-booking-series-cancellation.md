# 0023. Recurring Booking Series cancellation scopes and Series read

## Status

Accepted

## Context

ADR 0019 materializes weekly Booking Occurrences under a Recurring Booking Series. ADR 0022 confirms payment and expires unpaid holds. Members and Operators still cannot cancel a single occurrence, that occurrence and every later one, or the remaining Series without rewriting historical Booking rows.

Church rental policy and spec #139 require scoped cancellation that keeps historical occurrences intact, the same rules for member and admin on-behalf administration, and Series reads that expose occurrence and payment state for My Bookings and Portal detail.

This ADR covers core-api#152. Refunds, price adjustments, and occurrence modification remain out of scope.

## Decision

### Scopes

Cancellation accepts only:

| Scope | Effect |
| --- | --- |
| `occurrence` | Cancel the selected future live occurrence and its slots. |
| `this_and_future` | Cancel the selected occurrence (if it is still future and live) and every later live occurrence. |
| `entire_series` | Cancel every remaining future live occurrence and mark the Series cancelled. |

A live occurrence is `pending_payment` or `confirmed` with `start_at` after cancel-time `now`. Historical rows (`start_at` at or before `now`), `cancelled`, and `overridden` occurrences are never rewritten.

`occurrence` and `this_and_future` require `occurrence_id` belonging to the Series. `entire_series` ignores `occurrence_id`. An unknown scope is rejected.

### Series status

- `entire_series` sets the Series to `cancelled` and clears `payment_hold_expires_at`.
- `occurrence` and `this_and_future` set the Series to `cancelled` only when no live occurrences remain.
- Repeating a cancellation that has already applied is a no-op that returns the current Series state.

### Authorization

- Member `GET` / `POST .../cancel` on `/api/v1/facility/booking-series/{series_id}` are owner-only (`user_id` is the Booker).
- Admin `GET` requires `facility:booking:read`. Admin cancel requires `facility:booking:update`.
- Member and admin share `RecurringBookingService` cancellation rules. Admin records Operator identity on cancelled occurrences via existing `cancelled_by_id` and Series audit `updated_by_id` / `updated_by`.

### Read

Member and admin Series GET return the same Series + occurrence contract used by create and payment confirmation: Series status, `payment_hold_expires_at`, quoted total, and every materialized occurrence status. Calendar/Grid continue to read Booking rows.

## Considered options

- Reuse one-time Booking cancel `single` / `series` — rejected. Those tokens do not distinguish this-and-future from entire-series, and one-time `series` currently only skips slot cancel.
- Soft-delete historical occurrence rows — rejected. Spec requires retained history.
- Separate occurrence-modification APIs — deferred with refunds and price adjustments.

## Consequences

- One-time `/bookings/{id}/cancel` is unchanged. Recurring cancellation is a Series use case.
- No Alembic revision is part of this ticket.

## Related

- core-api#139 (spec), #151 / ADR 0022 (payment and expiry), #152 (this slice)
- ADR 0019 (Series aggregate)
