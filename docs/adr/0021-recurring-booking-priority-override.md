# 0021. Priority Ministry override of future Rental occurrences

## Status

Accepted

## Context

ADR 0019 records Priority vs Non-priority on Recurring Booking Series create but rejects occupancy for every Series kind. ADR 0020 lets Personal Rental and Non-priority Ministry Series omit conflicting dates. Church Activity precedence still needs an atomic override of future Personal Rental occupancy, without touching another Ministry occurrence or a Blackout, plus bilingual staff/booker notification and an override audit row per affected occurrence.

This ADR covers core-api#150. Booking Payment Confirmation as a mutating action remains #151; this slice only needs that permission in the RBAC catalog so override mail can resolve active operators.

## Decision

### Authorization

- The override path is Recurring Booking Series create when the Booker is a current primary or secondary steward of an Active Ministry with `has_priority_booking = true`.
- Non-priority Ministry Series keep the ADR 0020 exclusion flow. A steward whose Ministry is not priority cannot displace Rentals.

### Occupancy classification

- Preview and create load occupying confirmed slots (Pending-payment and Confirmed Bookings) per proposed occurrence.
- A Blackout remains `blackout` and is never overridden.
- Occupancy with `ministry_id` is a Ministry-to-Ministry conflict: not overridable. Preview (and create rejection context) include that Ministry's current primary steward display name and church login email.
- Personal Rental occupancy (`ministry_id` is null) whose Booking start is after create-time `now` is overridable for a Priority Ministry Series. Preview marks it `is_overridable`. Create displaces those Bookings instead of failing.
- Past Rental occupancy is not overridable and remains a scheduling conflict (or an explicit exclusion).

### Atomic override

- In the create transaction, each overridable Rental Booking is marked `overridden`, its slots are cancelled, and one `facility.booking_override_log` row is written per overlapping room.
- `facility_booking_id` is the new Church Activity occurrence, `overridden_booking_id` is the displaced Rental, `overridden_by_id` is the Operator, `outcome` is `override_applied`.
- Failure before commit leaves no partial override. Mail is sent after the writes and must not roll them back.

### Notification

- Reuse Graph/Jinja bilingual mail (English block, then Traditional Chinese).
- Recipients are resolved at send time and deduplicated: the affected Rental Booker, active users granted `facility:booking_payment` (Booking Payment Confirmation), and the current incumbent of `DEACON_FACILITY`.
- Non-production `GRAPH_MAIL_OVERRIDE_TO` still redirects delivery. Delivery failure is logged and ignored.
- The message identifies affected dates, rooms, Church Activity name, and a My Bookings detail link. It does not include Ministry steward private contact.

### RBAC catalog

- Seed `facility:booking_payment` as a Facility child named Booking Payment Confirmation, `is_visible = false`, so Role Management can assign it without a sidebar item. Confirmation itself is #151.

## Considered options

- Separate override API after create — rejected. Spec requires atomic Series create plus override, not a two-step occupancy hole.
- Cancel displaced Rentals as `cancelled` only — rejected. `overridden` plus override-log outcome preserves auditor vocabulary already on the model.
- Wait for #151 before sending operator mail — rejected. Recipient resolution is part of this ticket; an empty operator list is valid until roles are granted.

## Consequences

- ADR 0019/0020 first-fail occupancy still applies when the Series is not Priority, and for Blackout / Ministry occupancy on Priority create.
- Clients should treat preview `is_overridable` as informational: Priority create will displace those Rentals without listing them in `excluded_dates`.
- A human-owned incremental RBAC seed is required for `facility:booking_payment`. No Alembic revision is part of this ticket.

## Related

- core-api#139 (spec), #150 (this slice), #151 (payment confirmation action)
- ADR 0019, ADR 0020, ADR 0012 (Graph/Jinja mail)
