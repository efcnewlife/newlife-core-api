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
How the admin booking management page presents bookings: `list`, `calendar`, or `grid`. Default is `list`. v1 syncs `view` and an ISO `date` (calendar/grid anchor day) into the page URL query; list may ignore `date`. Calendar week-vs-day is UI state only, not part of the URL. Calendar is the time overview of bookings: overlapping bookings are distinct clickable blocks in side-by-side lanes, up to a density cap; beyond that, occupancy is read on Grid. Grid is the single-day room-row occupancy view. List is the paginated record set.
_Avoid_: tab (UI chrome only), layout, perspective, treating Calendar and Grid as interchangeable concurrent-booking surfaces, summarizing concurrent Calendar bookings into one representative block

**Scheduling Conflict**:
A booking create or update rejected because a requested room interval overlaps a confirmed booking slot. Distinct from uniqueness conflicts (duplicate codes) and from Blackout overlap.
_Avoid_: generic "conflict", treating Blackout as the same failure, parsing the English detail string as the contract

**Blackout**:
A room-closed interval that makes the room unbookable. Overlap with a Blackout is a distinct rejection from a Scheduling Conflict; the client must show a different prompt.
_Avoid_: scheduling conflict, "closed" without naming the Blackout rule

### Org / ministry

**Annual Ministry**:
A ministry that runs as one distinct edition per year, with the year in its name (e.g. Alpha 2026). Next year's edition is a **new** Ministry record, not the same row with shifted dates, so each year keeps its own approval, stewards, and history.
_Avoid_: recycling last year's row by editing its dates, treating the year as a Seasonal schedule bound

**Seasonal schedule**:
An ongoing weekly Ministry whose pattern only applies inside a date window, expressed as `effective_from` / `effective_to` on its schedule rows (e.g. a Saturday class that pauses June through August). The Ministry stays a single record across seasons.
_Avoid_: one Ministry per season, calling a bounded weekly pattern an Annual Ministry
