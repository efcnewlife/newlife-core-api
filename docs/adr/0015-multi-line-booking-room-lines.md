# 0015. Member booking cart allows multiple booking_room lines per room

## Status

Accepted

## Context

Member facility booking is moving from a shared interval across up to three distinct rooms to a **Booking cart**: up to three **Booking lines**, each with its own `facility_id`, `start_at`, and `end_at`. The same room may appear on more than one line (different times on the same calendar day).

`facility.booking_room` already stores per-line `start_at` / `end_at`, and `BookingService.create_booking` already quotes and persists per-line intervals when `line.start_at` / `line.end_at` are set. The blocker is schema: `uq_booking_room_booking_facility` allows only one row per `(facility_booking_id, facility_id)`.

Admin Booking range query (ADR 0007) matches on the booking **header** interval. List filters use **Primary facility** (`facility.booking.facility_id`). Neither ADR changes; this ADR defines how header fields behave when lines differ.

## Decision

### Schema

- Drop `uq_booking_room_booking_facility` on `facility.booking_room`.
- Do **not** add a replacement unique on `(facility_booking_id, facility_id)`.
- Reject **exact duplicate lines** on create/update: same `facility_id`, `start_at`, and `end_at` on one booking.

### Member cart rules (v1)

- At most **3** `booking_room` rows per booking (`MAX_ROOMS_PER_BOOKING` policy continues to cap **line count**, not distinct room count).
- All lines must fall on the **same local calendar day** in the facility timezone (`SettingService.get_facility_timezone()`).
- Each line must satisfy `end_at > start_at` and must not cross local midnight (one continuous interval within that day).
- Member v1 create remains **One-time** (`booking_type = one_time`); Recurring is out of scope.

### Booking header envelope

On member create (and member-scoped update when applicable), set header `start_at` / `end_at` to the **envelope** of all lines:

- `start_at = min(line.start_at)`
- `end_at = max(line.end_at)`

Persist each line's own interval on `booking_room` and expand `booking_slot` per line (unchanged pattern). Scheduling Conflict and Blackout checks remain **per line interval**.

### Primary facility

- `facility.booking.facility_id` remains the list Primary facility: the `facility_id` of the line with the lowest `sequence` (first cart line).
- ADR 0007 range query continues to use header overlap; envelope keeps multi-line bookings visible for the full occupied span.

### Admin API

- Admin create/update already accepts per-line times; no contract break.
- Admin serializers may return multiple `booking_room` rows for the same `facility_id`; consumers must not assume one row per room.

## Consequences

- Member cart can book Room A 9:00-11:00 and Room A 14:00-16:00 in one booking.
- Occupancy and conflict detection stay correct via per-line slots.
- List rows still show one header interval (envelope) and one Primary facility; detail and Grid must read **lines**, not header alone, when intervals differ.
- `newlife-portal-frontend` ADR 0002 ("one booking, one interval on every facilityIds row") is **superseded for occupancy drawing** when this ships; track in portal-frontend separately.
- Do not reintroduce `(booking_id, facility_id)` uniqueness without superseding this ADR.

## Related

- core-api#122
- facility-booking-frontend#68, #71, #73
- ADR 0001 (error codes), ADR 0007 (range query) — unchanged
