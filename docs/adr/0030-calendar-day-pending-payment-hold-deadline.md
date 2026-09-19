# 0030. Calendar-day Pending-payment hold deadline

## Status

Accepted

## Context

The previous `facility.pending_payment_hold_hours` policy described an exact elapsed-time deadline. Church payment handling instead needs a predictable facility-local cutoff: morning bookings receive the midday cutoff three calendar days later, and afternoon bookings receive the following midnight.

## Decision

- Replace `facility.pending_payment_hold_hours` with `facility.pending_payment_hold_days`, a positive integer whose default is 3.
- Calculate each new deadline in `facility.timezone`. When the local creation time is before 12:00, set it to 12:00 on `created_local_date + hold_days`; otherwise set it to 00:00 on `created_local_date + hold_days + 1`.
- Treat 12:00 as the latter case. Midnight is an exclusive deadline: payment confirmation and occupancy remain valid only strictly before it.
- Keep an existing Series' persisted `payment_hold_expires_at` unchanged. The new calculation applies only to newly created Series.
- Migrate an existing hours value only when it is a multiple of 24 (`72` becomes `3`). A non-multiple requires an explicit administrator decision rather than a guessed conversion.
- Replace the public `pendingPaymentHoldHours` field with `pendingPaymentHoldDays`; keep `paymentHoldExpiresAt` as the authoritative absolute deadline.

## Consequences

`paymentHoldExpiresAt` remains an absolute API value, but it is no longer exactly the configured count multiplied by 24 hours. This supersedes the **Hold duration** section of ADR 0022; its confirmation, query-time expiry, sweep, and notification decisions remain in force.
