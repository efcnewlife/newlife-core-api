# 0022. Recurring Booking payment confirmation and pending-payment expiry

## Status

Accepted

## Context

ADR 0019 creates a Recurring Booking Series as `pending_payment`, reserves occupancy with confirmed slots, and stores `payment_hold_expires_at` from `facility.pending_payment_hold_hours` (default 72). ADR 0021 seeds `facility:booking_payment` (Booking Payment Confirmation) as a hidden Facility child so override mail can resolve operators. Manual confirmation and the unpaid-hold expiry sweep remain unimplemented.

Church rental policy requires full payment before a Series is Confirmed. Unpaid holds must expire after the configured duration even when multiple API workers run, and availability must not wait for physical cleanup.

This ADR covers core-api#151.

## Decision

### Confirmation

- Admin `POST /admin/api/v1/facility/booking-series/{series_id}/confirm-payment` is protected by `facility:booking_payment:update` (Booking Payment Confirmation). It is not authorized by general Booking modify.
- `RecurringBookingService.confirm_payment` transitions the Series and every remaining `pending_payment` occurrence to `confirmed` in one use case. Already cancelled or overridden occurrences stay unchanged.
- The Operator is recorded on the Series via existing audit `updated_by_id` / `updated_by`. No new persistence column is added in this slice.
- Confirming an already-confirmed Series is a no-op that returns the current confirmed state. Confirming a missing Series is not found. Confirming a cancelled or expired Series is rejected.

### Hold duration

- Superseded by ADR 0030. New Series use `facility.pending_payment_hold_days` and a facility-local noon/midnight cutoff. Existing persisted `payment_hold_expires_at` values remain unchanged.

### Query-time logical expiry

- Occupancy reads treat a `pending_payment` occurrence as released when its Series `payment_hold_expires_at` is at or before query time, even if slots are still `confirmed`.
- Apply that filter to availability overlap, Recurring conflict occupying slots, and Weekly Rental Booking quota reads.

### Expiry sweep

- `RecurringBookingService.expire_pending_holds` is the expiry use case. It selects `pending_payment` Series whose hold has elapsed, cancels those Series and remaining pending occurrences (and their slots), then notifies the Booker.
- A FastAPI lifespan task runs the use case at startup (catch-up) and every 15 minutes.
- The sweep takes a PostgreSQL session-level advisory lock (`pg_try_advisory_lock`) before selecting work. If the lock is not acquired, the run is a no-op. The lock is released after commit or rollback so another worker cannot re-select uncommitted Pending-payment rows.
- Repeating the sweep after a successful expiry finds no `pending_payment` holds and does not re-cancel or re-send mail.

### Payment-hold expiry email

- Send a separate bilingual (English then Traditional Chinese) email to the Booker only. It lists released occurrences, the former Series payment total, and a Start Booking link.
- Delivery uses the existing Graph/Jinja path, including non-production recipient override. Failure is logged and does not retain the hold.

## Considered options

- A new `confirmed_by_id` column — deferred. Audit `updated_by_id` already records the Operator without a human migration in this slice.
- Redis lock for the sweep — rejected. Spec requires a PostgreSQL advisory lock so expiry stays correct with the same database workers use for occupancy.
- Blocking booking APIs until the sweep finishes — rejected. Query-time logical expiry is the availability contract.

## Consequences

- `init-rbac` remains the incremental catalog path for `facility:booking_payment`; this slice does not run `reset-rbac`.
- Calendar/Grid may still show a physically pending row until the sweep records cancellation; new occupancy must not.
- No Alembic revision is part of this ticket.

## Related

- core-api#139 (spec), #148 / ADR 0019 (create), #150 / ADR 0021 (payment permission catalog), #151 (this slice)
