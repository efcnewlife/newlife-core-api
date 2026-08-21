# 0007. Booking range query for Calendar and Grid

## Status

Accepted

## Context

Admin List correctly uses paginated `GET .../booking/pages`. Calendar and Booking Grid were loading the visible window through that same endpoint with `page=0` and a large `page_size`, which silently truncates busy windows and teaches the wrong contract. The pages date filter also matched `start_at` inside the window, not interval overlap, so bookings that span the window edge could be missing from occupancy views. Month Calendar layout (portal ADR 0006) widens the typical window and makes truncation more likely.

## Decision

Introduce a dedicated non-paginated **Booking range query** for Calendar and Booking Grid. List keeps `pages`.

- Required `date_from` / `date_to` (or equivalent). Return every non-deleted booking whose interval **overlaps** the window: `start < window_end` and `end > window_start` (half-open-friendly overlap, consistent with Calendar collision rules).
- Cancelled bookings are **excluded by default** and may be included via an explicit query flag.
- Cap the allowed window length (about 62 days — enough for a visible month grid, not an unbounded dump). Oversized windows are rejected.
- Response is a complete list for that window (list-item-shaped rows sufficient for Calendar/Grid), with no `page` / `page_size` completeness semantics.
- Portal Calendar and Grid both switch to this query; do not keep `pages` + large `page_size` as the occupancy contract.

## Consequences

- Occupancy surfaces can treat the payload as complete for the visible window.
- List pagination and occupancy reads stay separate mental models and APIs.
- Callers must keep UI ranges inside the window cap; Month/Week/Day/Grid visible ranges from the portal fit.
- Do not reintroduce silent truncation via paginated List pages for Calendar/Grid without superseding this ADR.
