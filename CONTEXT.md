# NewLife Core

Portal backend for church admin operations: auth/RBAC, facility booking, org/ministry, and related platform services.

## Language

### Facility booking

**Booker**:
The user who owns the booking (`user_id`). Ministry membership and booker-facing rules apply to this person, not to whoever submitted the create request.
_Avoid_: owner (ambiguous), customer, member (role-specific), on-behalf user

**Operator**:
The authenticated admin (or member) who performed the create action. For admin on-behalf create, Operator differs from Booker. v1 records Operator only via immutable audit `created_by_id` / `created_by` — no dedicated business column — and shows them on admin booking **detail** as Created by (always, including when Operator equals Booker).
_Avoid_: admin (role, not the act), creator (too generic), booked-by field, 代訂人-only label when self-booked

**Primary facility**:
The booking's main room id used for list filters and v1 Room×Time grid placement (`facility_id` / list `facilityId`). For multi-room bookings this is the first room line; other rooms are not drawn as separate grid blocks in v1.
_Avoid_: room (ambiguous when multiple), main room (synonym drift)

**Booking view mode**:
How the admin booking management page presents bookings: `list`, `calendar`, or `grid`. Default is `list`. v1 syncs `view` and an ISO `date` (calendar/grid anchor day) into the page URL query; list may ignore `date`. Calendar week-vs-day is UI state only, not part of the URL.
_Avoid_: tab (UI chrome only), layout, perspective

**Scheduling Conflict**:
A booking create or update rejected because a requested room interval overlaps a confirmed booking slot. Distinct from uniqueness conflicts (duplicate codes) and from Blackout overlap.
_Avoid_: generic "conflict", treating Blackout as the same failure, parsing the English detail string as the contract

**Blackout**:
A room-closed interval that makes the room unbookable. Overlap with a Blackout is a distinct rejection from a Scheduling Conflict; the client must show a different prompt.
_Avoid_: scheduling conflict, "closed" without naming the Blackout rule
