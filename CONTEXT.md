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
The booking's main room id used for list filters (`facility_id` / list `facilityId`). For multi-room bookings this is the first room line.
_Avoid_: room (ambiguous when multiple), main room (synonym drift), treating Primary facility as the only room shown on Booking Grid

**Booking view mode**:
How the admin booking management page presents bookings: `list`, `calendar`, or `grid`. Default is `list`. v1 syncs `view`, an ISO `date` (calendar/grid anchor day), and when `view=calendar` the Calendar layout (`week` / `day` / `month`) into the page URL query; list may ignore `date` and layout. Calendar is the time overview of bookings: overlapping bookings are distinct clickable blocks in side-by-side lanes, up to a density cap; beyond that, occupancy is read on Grid. Month Calendar layout is a month grid of compact booking summaries plus the selected day's time-axis. Grid is the single-day room-row occupancy view: a multi-room booking appears on every occupied room row. List is the paginated record set. Calendar and Grid load bookings via a Booking range query for the visible window, not via List pagination.
_Avoid_: tab (UI chrome only), layout as a synonym for Booking view mode, perspective, treating Calendar and Grid as interchangeable concurrent-booking surfaces, summarizing concurrent Calendar bookings into one representative block, using paginated List pages as the Calendar/Grid completeness contract

**Booking range query**:
A non-paginated admin read: every booking whose interval overlaps a required time window. Used by Calendar and Booking Grid so the visible window is complete. Matching is interval overlap, not `start_at`-in-window. Cancelled bookings are omitted by default and may be requested via an explicit flag. The allowed window length is capped. Distinct from the paginated List `pages` query.
_Avoid_: List `pages` with a large page size, silent truncation as acceptable Calendar/Grid behavior, `start_at`-only window filters for occupancy views

**Scheduling Conflict**:
A booking create or update rejected because a requested room interval overlaps a confirmed booking slot. Distinct from uniqueness conflicts (duplicate codes) and from Blackout overlap.
_Avoid_: generic "conflict", treating Blackout as the same failure, parsing the English detail string as the contract

**Blackout**:
A room-closed interval that makes the room unbookable. Overlap with a Blackout is a distinct rejection from a Scheduling Conflict; the client must show a different prompt.
_Avoid_: scheduling conflict, "closed" without naming the Blackout rule

### Org / ministry

**Ministry**:
A church organizational unit with localized names, a ministry type, and a lifecycle status.
_Avoid_: MinistryType (catalog), Ministry Application (the submit-for-approval request)

**Ministry Type**:
A catalog classification of a Ministry: Outreach, Internal, or Worship.
_Avoid_: Ministry, free-text type on the Ministry row

**Active**:
The Ministry lifecycle status after approval. Booking and owned-ministry lists include Active Ministries.
_Avoid_: Approved as a Ministry status, using Approval status in place of Ministry status

**Ministry Approval**:
A submit-and-decide record on a Ministry. Its status is pending, approved, or rejected. Approving it moves the Ministry to Active.
_Avoid_: treating Approval status as the Ministry's own status

**Ministry Member**:
A primary or secondary steward on a Ministry who may book on behalf of that Ministry.
_Avoid_: member (church person), Booker, owner position

**Annual Ministry**:
A Ministry that occurs once per calendar year (or that year's season). Each year is a new Ministry record.
_Avoid_: mutating last year's Ministry to reuse it, treating effective_from / effective_to as a forever-recurring annual rule

**Seasonal schedule**:
`effective_from` / `effective_to` on a schedule row that bound when a weekly pattern applies during that Ministry's life (for example except summer).
_Avoid_: opening a new Ministry each season for an ongoing weekly program, confusing this with Annual Ministry

**Ministry Steward**:
A user assigned to a Ministry as `primary` or `secondary` (`org.ministry_member`). This is who may represent the Ministry. It is not a pastoral Person record and not the facility-booking priority-member identity.
_Avoid_: Ministry Member (when meaning booking priority), Member Person, owner (Position incumbent)

**Steward roster**:
The full set of Ministry Stewards for one Ministry. Domain rule: exactly one primary steward and at least one secondary steward.
_Avoid_: treating primary/secondary as auth.role or org.position

**Steward directory query**:
A query whose result is Ministries, not membership rows. It may match a Ministry name or a Steward's display name/email. A match does not return the Steward roster; the roster loads for the selected Ministry.
_Avoid_: one row per steward, treating this as Member Person search, stuffing the roster into the directory payload

**Annual Ministry**:
A ministry that runs as one distinct edition per year, with the year in its name (e.g. Alpha 2026). Next year's edition is a **new** Ministry record, not the same row with shifted dates, so each year keeps its own approval, stewards, and history.
_Avoid_: recycling last year's row by editing its dates, treating the year as a Seasonal schedule bound

**Seasonal schedule**:
An ongoing weekly Ministry whose pattern only applies inside a date window, expressed as `effective_from` / `effective_to` on its schedule rows (e.g. a Saturday class that pauses June through August). The Ministry stays a single record across seasons.
_Avoid_: one Ministry per season, calling a bounded weekly pattern an Annual Ministry
