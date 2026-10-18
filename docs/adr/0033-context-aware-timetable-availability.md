# 0033. Context-aware Timetable availability and conflict redaction

## Status

Accepted

## Context

Member availability previously returned only free AM/PM intervals. Occupied and Closed time disappeared from the Timetable, Personal and Ministry discovery shared the same room filter, and Series conflict preview could expose Ministry steward contacts on Personal proposals. EFC-254 / EFC-255 require authoritative full-day cells, context-dependent room visibility, and authorized contact projection.

## Decision

- `GET /api/v1/facility/rooms/availability` returns `facilityTimezone`, live `maxBookingLines`, room/photo metadata, applicable `templates` (`start`, `end`, `slotDurationMinutes`), and 48 half-hour `cells` with states `available` / `unavailable` / `override` / `closed`.
- AM/PM freelists remain additive for compatibility but are derived only from Available cells. Override time is never listed as free. Cells and templates are authoritative for the frontend.
- Personal discovery omits rooms without a usable Available interval. Ministry discovery retains rooms whose non-Blackout opening time is fully occupied. Both omit rooms with no applicable template or no offered time outside Blackouts.
- Effective Pending-payment and Confirmed occupancy occupy cells (expired holds are already released by the occupancy clause). Ministry occupancy is Unavailable. Future Rental occupancy is Override only for an authorized Active Priority Ministry steward.
- Ministry-context items include distinct clipped `events` with authorized contacts (Ministry name + current primary steward, or Rental Booker for Non-priority). Personal items omit events and identifying contacts. Forged or unauthorized `ministry_id` is rejected.
- Series preview / Draft evaluation / conflict errors for Personal proposals normalize Ministry occupancy to generic `occupancy` without Ministry id or steward fields. Non-priority Ministry occupancy conflicts may include Booker contact for Rental targets.

## Consequences

- Facility Booking frontend Timetable must prefer cells/templates over AM/PM freelists.
- One-time Priority override acknowledgement and atomic confirmation remain later tickets (EFC-258); this ADR does not introduce `overrideReviewToken`.

## Related

- EFC-254 / facility-booking-frontend#155 (spec), EFC-255 / core-api#233 (this slice)
- ADR 0020 (conflict preview), ADR 0021 (Priority override on Series create)
