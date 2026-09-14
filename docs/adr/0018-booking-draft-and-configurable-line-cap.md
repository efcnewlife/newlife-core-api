# 0018. Booking Draft as a standalone resource; Booking line cap becomes a System Setting

## Status

Accepted

## Context

facility-booking-frontend's Booking Details page currently encodes date, ministry, and every Booking line directly into its own URL query (ADR 0016/frontend, ADR 0027/frontend) so a reload or pasted link reopens the same draft. Two problems came out of grilling the Timetable cart bugs: (1) the Timetable's own cart, before Review Booking, has no durable storage at all (fixed separately in facility-booking-frontend ADR 0028, via localStorage — no backend change), and (2) reusing a `facility.booking` row for a pre-confirm "draft" concept was considered and would require real backend work, not a shortcut.

`BookingStatus.DRAFT` (`portal/domain/facility/constants.py`) exists as an enum member but is unused end-to-end: nothing ever writes it, the Scheduling Conflict check (`has_confirmed_slot_overlap`) keys off the separate `BookingSlotStatus` (which has no DRAFT member) and would not exclude a DRAFT booking's slots from occupying the room, and `list_user_bookings` (`/bookings/mine`) applies no status filter at all, so a DRAFT row would appear in a member's own booking list today.

Separately, ADR 0017 hardcoded the 1-3 Booking line cap as "a hard product rule (serializers/constants), not a Policy Setting row," specifically to avoid resurrecting the per-room-scoped `FacilityRentalPolicySetting` pattern it deleted. Product now wants that cap raised and admin-configurable without a frontend deploy.

## Decision

### Booking Draft

- New standalone resource/table, not `facility.booking`. Stores only the member's proposed `date`, `ministry_id`, and lines (`facility_id`, `start_at`, `end_at`, `sequence`) plus an id and the creating `user_id`.
- Non-locking: creating or holding a Draft never marks a room Unavailable to other members. Price and availability are computed live from the stored lines on every `GET`/`PATCH` response — never cached on the Draft row.
- Auth-scoped to its creator only. A request for another user's Draft id, or one that no longer exists, returns the same not-found response as any other unauthorized/unknown resource.
- `POST /booking-drafts` is called from the Timetable's Review Booking action with the current cart; `PATCH /booking-drafts/{id}` updates it in place for Edit/Remove on Booking Details (last-write-wins; no optimistic-lock version field).
- Deleted in the same request that successfully creates the real `Booking` from it (`POST /bookings`, unchanged). An abandoned Draft that's never confirmed is not otherwise cleaned up in this slice — no expiry job.
- Both `POST` and `PATCH` re-validate the existing cart domain rules server-side (line count against the Booking line cap, same calendar day, no cross-midnight, at least 1 line) rather than trusting the client.

### Booking line cap

- Replace the hardcoded `MAX_BOOKING_LINES = 3` constant with a `facility.max_booking_lines` System Setting (`SettingValueType.NUMBER`, seeded value `10`, `is_built_in = true`).
- Global only — the generic `system_setting` table has no per-room/tenant scoping column, and this cap has never varied by room.
- `SettingService` gets a `get_max_booking_lines()` reader mirroring the existing `get_facility_timezone()` cache-then-DB pattern (Redis, invalidated on admin edit).
- The member availability response gains a `maxBookingLines` field so the Timetable reads the live value instead of hardcoding one; no new public settings endpoint.

## Considered options

- Reuse `facility.booking` + `BookingStatus.DRAFT` for the Draft — rejected. DRAFT is wired into nothing today; "reusing" it means newly building exclusion from conflict checks, `/bookings/mine`, and admin list/detail/cancel flows, which is more work and more risk than a small dedicated resource.
- Per-room `max_booking_lines` override, mirroring the deleted `FacilityRentalPolicySetting.facility_id` pattern — rejected. No room currently needs a different cap, and that per-scope side-table shape is exactly what ADR 0017 removed as a "dead catalog" risk.
- Snapshot price/availability on the Draft at creation time — rejected. Would reintroduce a form of staleness/locking the non-locking design is meant to avoid, for no read-latency win that matters at this scale.

## Consequences

- Booking Draft links are not shareable between members, unlike the query-based draft it replaces — a deliberate trade-off; see facility-booking-frontend ADR 0029.
- Reintroducing a per-room line cap, or resurrecting `BookingStatus.DRAFT` for anything, is a new decision, not flipping a dormant feature.
- `MAX_BOOKING_LINES` call sites (`booking_service.py`) move from a module constant to a `SettingService` read.

## Related

- ADR 0015 (original 1-3 line cap and cart rules; cap value itself now superseded here)
- ADR 0017 (line cap wording superseded here; minimum-fee removal unaffected)
- facility-booking-frontend ADR 0028 (Timetable cart in localStorage)
- facility-booking-frontend ADR 0029 (Booking Details consumes this Draft)
