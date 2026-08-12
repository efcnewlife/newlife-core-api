# Booking create/update uses machine-readable error codes

Clients cannot tell a Scheduling Conflict or Blackout from a generic 400 by reading English `detail`. We return a stable `error_code` (and `context.facility_id`) on those two failures, use HTTP 409 only for Scheduling Conflict, and leave other `ConflictErrorException` uniqueness responses unchanged until a follow-up.

## Considered Options

- **Parse `detail` strings** — rejected: locale- and wording-fragile; UUIDs leak into UI copy.
- **HTTP 409 only, no code** — rejected: uniqueness 409 (duplicate room code, etc.) would look the same to the client.
- **Stay on 400 for both, plus `error_code`** — workable, but Scheduling Conflict is a conflict with current slot state; 409 matches that. Blackout is a calendar rule, not occupancy, so it stays 400 with its own code.
- **Collect every conflicting room in one response** — deferred: first-fail is enough for v1 (at most a few rooms).
- **Populate `error_code` on every existing 409 now** — deferred: out of scope for the booking prompt; tracked separately.

## Consequences

- Exception JSON stays snake_case (`detail`, `error_code`, `context`), matching `debug_detail`.
- Codes: `FACILITY_BOOKING_SCHEDULING_CONFLICT` (409) and `FACILITY_BOOKING_ROOM_BLACKOUT` (400).
- `detail` remains human English for logs and unknown clients; the admin SPA must map `error_code` to i18n and must not parse `detail`.
- Frontend `ApiError.code` remains the HTTP status; the business token is a separate field (`error_code`).
