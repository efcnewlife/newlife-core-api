# 0016. Member preview-quote uses per-line intervals

## Status

Accepted

## Context

`POST /api/v1/facility/preview-quote` accepts one `start_at` / `end_at` and a room list. The mapper applies that single interval's billed hours to every room line (`member_preview_quote_to_command`). That matches the retired "shared interval + up to three rooms" UX, not the Booking cart where each line has its own time.

Admin `POST /admin/api/v1/facility/rental-rate/preview-quote` already accepts `billed_hours` per `room_lines` entry; only the **member** contract needs to change.

`PricingService.preview_quote` and booking create already support per-line `billed_hours`; this ADR is API-boundary only for the member surface.

## Decision

### Request contract

Replace the shared-interval member preview shape with **per-line times**:

- Request body carries **1-3 lines**, each with:
  - `facility_id` (required)
  - `start_at` (required)
  - `end_at` (required)
- Top-level `start_at` / `end_at` are **removed** from the member preview request (breaking change; no v1 dual-shape).
- Booking-level fields unchanged: `ministry_id`, `is_mission_aligned`, `currency`, `surcharge_codes`.

Example request shape (snake_case on the wire per member API convention):

```json
{
  "ministry_id": "...",
  "is_mission_aligned": false,
  "currency": "CAD",
  "surcharge_codes": [],
  "lines": [{ "facility_id": "...", "start_at": "...", "end_at": "..." }]
}
```

### Validation

- `lines`: `min_length=1`, `max_length=3`.
- Each line: `end_at > start_at`.
- Same calendar-day and no cross-midnight rules as ADR 0015 (reuse shared validator where possible).
- Reject exact duplicate lines (same `facility_id`, `start_at`, `end_at`).
- Ministry gate and steward rules unchanged (`preview_quote_for_member`).

### Mapping and response

- `BookingService.preview_quote_for_member` validates lines (ADR 0015 rules), then sets `PreviewQuoteRoomLineCommand.billed_hours` from each line's `(start_at, end_at)`.
- Response shape (`roomLines`, totals) **unchanged**; each `roomLines[i]` reflects that line's interval and subtotal.
- Order of `room_lines` in the response matches request `lines` order.

### Create booking alignment

- Member `POST /api/v1/facility/bookings` should accept the same per-line interval shape and set header envelope per ADR 0015 so preview totals match create.

## Consequences

- facility-booking-frontend cart can quote after each ADD without forcing a shared interval.
- Breaking change for any client still sending top-level `start_at` / `end_at` + `rooms[]` only; coordinate with facility-booking-frontend#73.
- Admin preview-quote API unchanged.
- Tests that assert `member_preview_quote_to_command` copies one interval to all rooms must be replaced.

## Related

- core-api#123
- ADR 0015 (line rules and header envelope)
- facility-booking-frontend#73, #74
