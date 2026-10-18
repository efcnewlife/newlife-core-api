# 0034. Enforce member Room Slot Template opening hours

## Status

Accepted

## Context

Members could create One-time and Recurring Bookings outside applicable Room Slot Template windows because create/Draft/preview paths only checked occupancy and Blackout. EFC-254 / EFC-256 require server-side enforcement of template coverage and minimum duration for member proposals, while Administrator create retains an explicit opening-hours exception.

## Decision

- Member One-time create, Draft evaluation, and Recurring preview/evaluation/confirmation validate each interval against active templates for the facility-local day (effective dates, weekday mask, contiguous open windows, start-cell minimum `slot_duration_minutes`).
- Rejection uses stable `FACILITY_BOOKING_OUTSIDE_OPENING_HOURS` (HTTP 400). Scheduling Conflict and Room Blackout keep their existing codes and are checked first so template validation does not rebrand them.
- Administrator create maps `enforce_opening_hours=False` inside delivery mappers only; member serializers cannot set a bypass.
- Preview and final confirmation share the same rule so a template change after review fails before Booking creation.

## Consequences

- Facility Booking frontend maps `FACILITY_BOOKING_OUTSIDE_OPENING_HOURS` like Blackout (distinct copy).
- Longer member intervals need not be integer multiples of template duration; the template duration remains the minimum only.

## Related

- EFC-254 / facility-booking-frontend#155 (spec), EFC-256 / core-api#234 (this slice)
- ADR 0001 (booking error codes), ADR 0033 (Timetable cells/templates)
