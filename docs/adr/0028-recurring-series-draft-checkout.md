# Recurring Series Draft checkout

A Recurring Series Draft is a member-owned, non-locking review resource for one weekly Recurring Booking Series proposal. Confirming an owned valid Draft is the member path that creates a pending-payment Series; the Draft is consumed in the same request. This keeps Repeated Booking on the same Review / Booking Details / Payment journey as One-time Booking without widening Booking Draft to hold weekly-Series data.

## Context

One-time Booking already persists a Booking Draft (ADR 0018) and creates the Booking from Booking Details. Recurring Booking Series create was a direct `POST /booking-series` from the Repeated Review surface. That skipped a durable, reloadable review state and mixed a weekly proposal into a one-time Draft shape if we reused `facility.booking_draft`.

facility-booking-frontend #125 and ADR 0034 require a separate Recurring Series Draft contract so Preview-ready Repeated proposals can survive refresh, retain Title and permitted exclusions, revalidate before Confirm, and create exactly one Series.

## Decision

- Add `facility.booking_series_draft` plus ordered `facility.booking_series_draft_room` rows. Store the weekly schedule (`first_occurrence_date`, `last_occurrence_date`, `local_start_time`, `local_end_time`), optional Title, ministry, surcharge codes, remark, permitted `excluded_dates`, and ordered rooms. Do not store quote, availability, or payment-hold expiry on the row; those are computed live on every read and on Confirm.
- The Draft never reserves rooms. Missing, consumed, or another member's Draft returns the same not-found response (`FACILITY_BOOKING_SERIES_DRAFT_NOT_FOUND`).
- Member API (separate from Booking Draft and from created Series):
  - `POST /api/v1/facility/booking-series-drafts` — persist a structurally valid preview-ready proposal
  - `GET /api/v1/facility/booking-series-drafts/{id}` — owner read with live conflicts, quote, payment-hold hours, and `isConfirmable`
  - `PATCH /api/v1/facility/booking-series-drafts/{id}` — replace the proposal after a fresh preview (last-write-wins)
  - `POST /api/v1/facility/booking-series-drafts/{id}/confirm` — revalidate; if confirmable, create one pending-payment Series and delete the Draft; otherwise `FACILITY_BOOKING_SERIES_DRAFT_NOT_CONFIRMABLE` with `invalidity_code` and current conflicts
  - `DELETE /api/v1/facility/booking-series-drafts` — clear the member's unconfirmed Recurring Series Drafts only
- Confirm requires a valid Title and the same policy/conflict rules as `RecurringBookingService.create_series`. Admin `POST /admin/api/v1/facility/booking-series` is unchanged.
- Agents must not add or edit `alembic/versions/**`. A human migration must create the two tables; suggested columns live on the ORM models.

## Considered options

- Extend Booking Draft lines with weekly-Series fields — rejected. One-time lines are independently timed; a Series has one shared window and proposal-specific exclusions.
- Keep direct member `POST /booking-series` as the only create path — rejected. It cannot reload a review or prevent double submit after refresh.
- Snapshot quote and conflicts on the Draft row — rejected. Stale cached occupancy would look confirmable.

## Consequences

- Member Repeated checkout no longer needs to encode the weekly proposal in the URL. Direct member Series create can remain for compatibility; the frontend Confirm path uses Draft confirmation.
- Until the human migration runs, local/dev databases will not persist Recurring Series Draft rows even though the application code is present.

## Related

- ADR 0018 (Booking Draft)
- ADR 0019 / 0020 (Series create and conflict preview)
- facility-booking-frontend ADR 0034
- core-api#198, facility-booking-frontend#125
