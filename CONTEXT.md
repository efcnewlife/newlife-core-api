# NewLife Core

Portal backend for church admin operations: auth/RBAC, facility booking, org/ministry, and related platform services.

## Language

### Facility booking

**Mock user**:
A randomly generated QA member identity used to exercise Facility Booking with real Mock login authorization and business relationships. A Mock user is neither a production member nor a privilege bypass.
_Avoid_: demo user, production account, superuser, fake frontend session

**Testing account**:
The `@test.local` account credential of a Mock user that is eligible for Mock login when it is verified and active. It is the login qualification, not the user's business persona.
_Avoid_: Mock user as a synonym for the credential, production login, admin account

**Mock fixture**:
A run-scoped, near-term generated test entity associated only with Mock users. Mock fixtures cover display and QA scenarios for Ministries, Bookings, slot templates, and Blackouts, and are distinguishable from real data by their Mock run identity.
_Avoid_: fixed demo data, a production fixture, a non-login test record

**Mock run identity**:
The environment-and-minute identity shared by one complete Mock fixture generation run. It links the run's machine-readable markers and display labels without replacing an individual Testing account's random email suffix.
_Avoid_: an account persona, a credential, a user-facing fixture purpose

**Mock run marker**:
The machine-readable `mock:` identity, including a Mock run identity, carried by a Mock-owned fixture that is not otherwise linked to a Testing account. It permits removal of that fixture without selecting manually created data.
_Avoid_: a user-facing display name, a broad cleanup wildcard, the legacy `seed:` marker

**Legacy demo fixture**:
The retired fixed local data bundle formerly used to display Ministries, Bookings, slot templates, and Blackouts. Its non-login `seed.*@local.test` Demo accounts are neither Mock users nor Testing accounts; new test fixtures are generated as Mock data instead. Leftover exact Demo-account identities and `seed:` markers are removed only by the opt-in `remove-mock-data --include-legacy-demo` transition, not by ordinary Mock cleanup.
_Avoid_: treating a legacy demo fixture as a supported QA credential, mixing it with generated Mock data, treating ordinary `remove-mock-data` as a demo-pack wipe

**Catalog bootstrap**:
The `init-all` command's catalog and configuration foundation for a new environment: locales, RBAC, system settings, positions, target audiences, facility rooms/rates, and Legal Documents, finishing with interactive superuser creation. It does not seed Ministry Types, Mock users, Ministries, Bookings, or other business fixtures. Re-running upserts existing catalog rows and never resets or deletes them.
_Avoid_: treating Mock fixtures or the retired local demo pack as bootstrap, requiring Ministry Type for a new environment, resetting catalog rows on re-run

**Recurring Booking Series**:
A scheduling rule and the materialized set of independently managed Booking occurrences it creates. It is distinct from each occurrence, which remains an individual Booking with its own lines and occupancy slots. It is not itself room occupancy.
_Avoid_: Repeated Booking, one infinite Booking row, an RRULE-only Booking, recurring Booking as a synonym for one occurrence, treating a Series as an occupancy record

**Booking Occurrence**:
One independently managed Booking created by a Recurring Booking Series. It follows the normal Booking lifecycle and may be adjusted or cancelled without changing other Occurrences unless an explicit series-level action says otherwise.
_Avoid_: instance when the Booking aggregate is meant, assuming every Booking belongs to a Series, treating one occurrence cancellation as a Series cancellation

**Booker**:
The user who owns the booking (`user_id`). Ministry membership and booker-facing rules apply to this person, not to whoever submitted the create request.
_Avoid_: owner (ambiguous), customer, member (role-specific), on-behalf user

**Booking Participant**:
A user associated with a Booking as its Booker or as the current primary or secondary member of the Booking's Active Ministry. A Booking Participant may view the Booking but does not gain Booker ownership.
_Avoid_: Booker as every participant, delegated Booker, Ministry-owned Booking

**Booker self-service authority**:
The authority reserved for the Booker to edit a Booking title, cancel, view payment instructions for, or rebook an eligible Booking through member-facing flows. Booking Participants who are not the Booker have view-only access.
_Avoid_: Ministry-member cancellation authority, participant-as-Booker, shared self-service control

**Booking title**:
A required, editable, non-unique, trimmed 1-30-character plain-text label owned by one Booking. It is distinct from the optional Booking remark and from a Room or Ministry name; the Booker may edit it through self-service and an authorized Administrator may edit it separately without changing commercial terms.
_Avoid_: remark as the title, Booking reference, localized Room name, markup content, participant title editing, repricing on a title edit

**Recurring Booking Series title**:
A required, editable, non-unique, trimmed 1-30-character plain-text label owned by one Recurring Booking Series. It is copied to every new Booking Occurrence as its initial title, after which the Series and Occurrence titles are independently editable by the Booker.
_Avoid_: occurrence title as the Series title, an immutable scheduling label, a shared reference code, later Series-title propagation

**Current Ministry Booking Participant**:
A Booking Participant whose current primary or secondary membership of the Booking's Active Ministry grants view access to a Ministry-associated Booking. Leaving the Ministry removes that view access, including for historical Bookings.
_Avoid_: historical membership entitlement, permanent participant archive, former-member view access

**Participant Booking detail**:
The complete scheduling and lifecycle information a Booking Participant may view: rooms, times, status, reasons, remark, price, and the Booker's name and email. Payment instructions remain Booker-only and Booker identity appears in detail rather than a list card.
_Avoid_: anonymous Booking detail, participant payment authority, hiding Booker identity

**My Bookings**:
The member-facing collection of Bookings in which the authenticated user is a Booking Participant. Its collapsible Upcoming, Overridden, Past, and Cancelled or Expired sections organize Booking records; Upcoming is initially expanded. Recurring Booking Occurrences are presented under their Recurring Booking Series, and each section is paginated.
_Avoid_: calendar-only view, a Booker-only list, flat recurring-occurrence list

**Member cancellation reason**:
The required 1-250-character explanation a Booker provides when cancelling a Booking or Recurring Booking Occurrence through My Bookings. For a multi-occurrence cancellation it is retained on every affected Occurrence as the lifecycle reason visible in Booking detail.
_Avoid_: silent member cancellation, optional explanation, an internal-only reason

**Booking lifecycle timeline**:
The ordered record of a Booking's creation and lifecycle outcome events, including cancellation, override, and pending-payment expiry when they occur. It is part of complete Booking detail but does not expose an Operator or a replacement Ministry or activity; title revisions are not lifecycle events.
_Avoid_: a status-only detail, an admin audit-log substitute, hiding an expiry as a missing Booking, cross-Ministry activity disclosure, title revision history

**Operator**:
The authenticated admin (or member) who performed the create action. For admin on-behalf create, Operator differs from Booker. v1 records Operator only via immutable audit `created_by_id` / `created_by` — no dedicated business column — and shows them on admin booking **detail** as Created by (always, including when Operator equals Booker).
_Avoid_: admin (role, not the act), creator (too generic), booked-by field, 代訂人-only label when self-booked

**Primary facility**:
The booking's main room id used for list filters (`facility_id` / list `facilityId`). For multi-line bookings this is the lowest `sequence` line's `facility_id` (first cart line), not the only room on the booking.
_Avoid_: room (ambiguous when multiple), main room (synonym drift), treating Primary facility as the only room shown on Booking Grid, assuming one `booking_room` row per room

**Booking line**:
One room interval on a booking: `facility_id`, `start_at`, `end_at`, and `sequence`. A booking may hold up to the Booking line cap lines. The same room may appear on more than one line with different intervals on the same local calendar day. Distinct from Primary facility and from the booking header envelope.
_Avoid_: room (when meaning a line), cart item without times, assuming one row per room in `booking_room`, assuming the cap is a fixed 3

**Booking line cap**:
The maximum number of Booking lines one booking may hold, read from the `facility.max_booking_lines` System Setting (NUMBER, default 10, global — not per-room). Enforced on both Booking Draft and booking create; the member Timetable reads the live value from the availability response so it never drifts from what the server enforces. Supersedes ADR 0017's hardcoded 1-3 rule.
_Avoid_: a per-room override, a value baked into frontend code, treating 3 as still correct

**Recurring Booking time window**:
The one local start and end time shared by every Booking line in every occurrence of a Recurring Booking Series. After it is selected, no different time window may be added to that Series.
_Avoid_: per-room time windows, a series with mixed intervals, treating a Booking header envelope as the Series time window

**Recurring Booking local time**:
The facility-local wall-clock time used for every Recurring Booking occurrence. A Series with a nonexistent local time on a DST transition is rejected; an ambiguous time uses the earlier offset.
_Avoid_: a UTC recurrence that drifts on DST, silently shifting a nonexistent time, choosing a later ambiguous offset

**Church Activity Booking**:
A Ministry-associated Booking for a church activity, distinct from an individual member's Rental Booking. Only one made for a Priority Ministry takes precedence over Rental Bookings when their future room intervals conflict.
_Avoid_: Ministry rental, assuming every Church Activity Booking has priority, personal Booking with priority

**Priority Ministry**:
An Active Ministry whose `has_priority_booking` is true and whose current primary or secondary steward may create a Church Activity Booking that replaces conflicting future Rental occurrences. Removing priority does not rewrite existing Series or override audit, but blocks future overrides.
_Avoid_: every Active Ministry, a Ministry with a priority member, a Ministry that may replace another Church Activity Booking, retroactively changing existing overrides

**Non-priority Ministry Series**:
A Recurring Booking Series made for an Active Ministry by its current steward when that Ministry is not a Priority Ministry. It may be created but does not replace conflicting Rental occurrences and follows the Rental conflict-resolution flow.
_Avoid_: blocking all non-priority Ministry Series, treating it as a Priority Ministry Series, silently overriding a Rental occurrence

**Facility Booking eligible account**:
An authenticated account whose email uses the church domain. This is the current eligibility gate for Rental Booking; no additional membership profile is maintained.
_Avoid_: a separate membership-status check, treating every external authenticated account as eligible

**Recurring Booking period**:
One fixed half-calendar-year window for recurring use: January through June or July through December. A Recurring Booking Series and all its occurrences stay within one such period.
_Avoid_: rolling six months, a Series that crosses the June-July boundary, a perpetual schedule

**Recurring Booking opening date**:
The facility-local calendar date one month before a Recurring Booking period begins, when that period becomes bookable: December 1 for January through June, and June 1 for July through December.
_Avoid_: a rolling booking horizon, opening on the first occurrence date, a UTC-based cutoff

**Recurring Booking availability window**:
The facility-local duration after a Recurring Booking opening date during which the corresponding Recurring Booking period accepts new Series. The built-in `facility.recurring_booking_availability_window` System Setting is an object with a positive `amount` and a `days`, `weeks`, or `months` unit; months are calendar-relative. Members can read whether a Series may be started now (optionally for a First occurrence date) via `GET /api/v1/facility/booking-series/availability-window`.
_Avoid_: confusing availability with a Series use period, a months-only numeric setting, treating four weeks as one calendar month

**Recurring Booking test-window override**:
A Boolean System Setting that makes the Recurring Booking availability window open without changing that window's configured business policy. It applies uniformly to every Booker in its non-production environment, is ignored in production, and is closed when absent, inactive, or invalid; it is not an account privilege.
_Avoid_: Repeated booking bypass, test-user exception, changing the availability-window setting for a test run, deployment-only flag

**Recurring Booking test Booker allowlist**:
A System Setting with separate exact email-address and whole-domain-suffix lists that makes matching Testing Accounts eligible to create a Recurring Booking Series. It is ignored in production, is closed when absent, inactive, or invalid, and does not make an unlisted account eligible.
_Avoid_: a blanket Mock-user exemption, substring matching, an administrator role bypass

**Recurring Booking minimum duration**:
The Booker selects first and last occurrences within one Recurring Booking period, and `facility.min_recurring_booking_weeks` requires at least four unexcluded weekly occurrences.
_Avoid_: a fixed mandatory six-month Series, a per-room minimum-duration policy, counting excluded occurrences toward the minimum

**Pending-payment Booking**:
A Booking that reserves its requested room intervals in first-come order but is not Confirmed until full payment is verified. It is distinct from a non-locking Booking Draft.
_Avoid_: Booking Draft, a Confirmed Booking before payment, a non-blocking payment request

**Weekly Rental Booking quota**:
The rule that a Booker may have no more than one Rental Booking occurrence from Sunday 00:00 through Saturday 23:59:59 in a facility-local calendar week, across one-time and recurring Rental Bookings. Pending-payment Bookings count toward this quota. Priority and Non-priority Ministry Series do not.
_Avoid_: one Booking per room per week, counting a multi-room occurrence more than once, applying the quota to Church Activity Bookings

**Booking occurrence exception**:
An individual occurrence that is cancelled or changed without changing the rest of its Recurring Booking Series. An omitted conflicting occurrence is a cancellation exception.
_Avoid_: editing the Series when only one occurrence changes, deleting an occurrence with no retained history

**Occurrence cancellation scope**:
The target of a member or Operator cancellation: `occurrence` (one Booking Occurrence), `this_and_future` (that occurrence and every later one), or `entire_series`. Historical, cancelled, and overridden occurrences are retained and not rewritten. Member and admin views both present occurrences under their Series. Occurrence modification is deferred from this slice.
_Avoid_: an unexplained raw RRULE edit, a Series-only management screen, applying a one-occurrence cancellation to all occurrences, reusing one-time Booking cancel `single`/`series` tokens

**Recurring Booking conflict preview**:
A server-backed review of a proposed Recurring Booking Series that lists every unavailable occurrence and distinguishes occupancy, Blackout, and Weekly Rental Booking quota conflicts. For a valid weekly proposal it also returns the Series Estimated Total (`quotedAmount` + `currency`) for the full generated occurrence set before conflict exclusions, using the same quoting path as Recurring Series Draft evaluation. It does not create a Series, Draft, or reserve slots. Occupancy and Blackout conflicts name the affected rooms; quota conflicts are week-level.
_Avoid_: treating preview as a reservation, collapsing occupancy and Blackout into one error, returning only the first conflict, inventing a client-side Series total, excluding conflict dates from the preview quote

**Recurring Booking conflict resolution**:
The choice presented when creating a Rental Recurring Booking Series conflicts with existing occupancy or a Blackout: omit all conflicting occurrences and create the rest, or revise the requested rooms and time window. A Church Activity Booking may replace conflicting future Rental occurrences, but never another Church Activity Booking. Omissions must be dates the current preview reported as conflicts; the server rejects arbitrary exclusions and revalidates the remaining dates in the create transaction.
_Avoid_: partial creation without user approval, silently overwriting an existing Church Activity Booking, treating a Blackout as overwritable occupancy, excluding a free date to shrink a Series

**Pending-payment hold expiry**:
The global payment deadline for an unpaid Pending-payment Booking, calculated from a configurable number of facility-local calendar days. A Booking created before noon expires at noon on the target day; one created at or after noon expires at the following midnight, while an existing stored deadline never changes. A FastAPI lifecycle sweep runs at startup and every 15 minutes under a PostgreSQL advisory lock; availability queries treat an elapsed expiry as released even before the sweep records cancellation.
_Avoid_: an exact elapsed-hours hold, an indefinite payment hold, a non-blocking payment request, an in-process timer with no cross-worker lock, a per-room payment deadline

**Payment-hold expiry email**:
An email to the Booker when a Pending-payment Series expires, listing released occurrences and the former Series payment total and linking to start a new Booking. Failure to deliver it does not prevent expiry.
_Avoid_: retaining the hold until email succeeds, an unexplained disappearance from My Bookings, reusing an override email

**Booking payment confirmation permission**:
The separate Facility permission that authorizes an Operator to mark a Pending-payment Booking as paid and Confirmed. It is displayed as Booking Payment Confirmation under Facility in the Role Permission matrix and is not a side-menu item.
_Avoid_: general Booking modify permission, an undiscoverable permission code, a new Role Management screen

**Series payment total**:
The server-computed total for all unexcluded occurrences in a Recurring Booking Series within its Recurring Booking period, recalculated in the creation transaction and due in full before that Series is Confirmed.
_Avoid_: one payment per occurrence, a client-computed total, confirming a partly paid Series

**Booking override email**:
An English-first, Traditional-Chinese-second email notifying an affected Rental Booker, active Booking Payment Confirmation Operators, and the current incumbent of the `DEACON_FACILITY` position that a Church Activity Booking has overridden specified future Rental occurrences. It identifies the affected dates and rooms and directs recipients to the authorized booking detail for the audit context. Recipients are resolved when sending and deduplicated.
_Avoid_: a generic cancellation email with no override reason, a seed email as the Facility Deacon, exposing Ministry steward private contact information to unapproved recipients, rolling back a successful override because email delivery fails

**Booking header interval**:
`facility.booking.start_at` / `end_at` on the master row. For multi-line member bookings, these are the **envelope** (earliest line start, latest line end). ADR 0007 range query and member list rows use this interval. Per-line occupancy and pricing use each Booking line.
_Avoid_: treating header times as the only interval when lines differ, using header alone for Grid bars when lines differ

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
A room-closed interval that makes the room unbookable, including for Church Activity Bookings. Creating a Blackout that overlaps a future occurrence cancels that occurrence after operator confirmation. Refund handling for that cancellation is deferred. Overlap with a Blackout is a distinct rejection from a Scheduling Conflict; the client must show a different prompt.
_Avoid_: scheduling conflict, "closed" without naming the Blackout rule, leaving an active Booking inside a Blackout

**Blackout impact preview**:
A server-backed review of a proposed Blackout that lists live future Recurring Booking Occurrences whose room intervals overlap it. It does not persist a Blackout or cancel occupancy. Confirmation requires the operator to resubmit the exact occurrence ids from this preview; the server then cancels only those occurrences and records `cancelled_by_id` / `cancel_reason`.
_Avoid_: persisting first then previewing, confirming a subset of the impact set, treating a Blackout as overridable occupancy, writing a Priority override log for this cancellation, cancelling one-time Bookings in this slice

**Room gallery**:
An optional ordered set of at most ten image Content Files bound to one Room. Each file appears at most once in that gallery. The same Content File may appear in many Rooms' galleries. Order is Operator-controlled (including drag reorder on the Room form). Saving the Room replaces the whole gallery. Soft-deleting a Room keeps its File associations so restore brings the gallery back. Admin Room list does not include gallery files; Room detail (and create response) does, with signed URLs for preview. Member availability includes those same signed photo URLs when files exist, or an empty list when none.
_Avoid_: cover, required gallery, room image URL field, treating the first file as a separate Cover entity in v1 admin, unbounded gallery, clearing associations on Room soft-delete, non-image Content Files, duplicate files in one gallery, list-page thumbnails as the v1 contract, a separate files GET for v1 admin preview

**Rental Rate Template**:
A shared billing rule for facility rental: unit amount, billing unit, and optional applicability (when the rule may be selected). Unit price always lives on the Template.
_Avoid_: putting a separate price on the Room binding, treating applicability as a booking Policy Setting

**Rental Rate**:
The binding of one Rental Rate Template to one Room, used when selecting which Template prices a Booking line. Distinct from the Template itself.
_Avoid_: Rate as a priced catalog row of its own, global NULL-facility Rate rows as the v1 model

**Preview quote**:
Server-computed rental totals for a proposed set of Booking lines (each with its own interval): per-line amounts from the selected Rental Rate Template, then booking-level ministry discount and surcharges. The quoted amount is line subtotals minus discount plus surcharges. There is no minimum-fee floor and no Rental Policy Setting in the pricing model. Distinct from creating a booking.
_Avoid_: client-side HST or totals, a single shared interval for all lines on member preview, treating Preview quote as a created booking, minimum fee / policy floor as part of the quote

**Booking Discount**:
An admin-managed percentage reduction of a Booking's room-line subtotal. An Active Ministry Booking whose Booker is its current primary or secondary member receives the Ministry Discount (30%); otherwise, a Recurring Booking receives the Recurring Discount (20%). Only one Booking Discount applies, and surcharges are added after the reduction. A configured percentage is from 0 to 100 with at most two decimal places; an inactive or absent rule is no discount.
_Avoid_: stacking Ministry and Recurring Discounts, discounting surcharges, a client-supplied discount amount

**Booking Discount Eligibility**:
The server-resolved result that identifies the one Booking Discount applicable to a proposed booking type, Ministry association, and Booker. It supports preflight display only; quote and create independently re-evaluate it.
_Avoid_: a Ministry-only discount checker, trusting a cached preflight for creation, a client-controlled `is_mission_aligned` flag

**Confirmed price snapshot**:
The persisted line-rate and Booking or Series financial values captured when a Booking becomes Confirmed. A Pending-payment Recurring Booking Series locks its quoted price when it is created, and payment confirmation does not reprice it. Later rate or discount-rule changes never reprice either snapshot.
_Avoid_: repricing a Confirmed Booking, retroactive discount-rule changes, a live total for historical Bookings

**Admin Booking edit**:
The limited admin change surface for an existing Booking: title, Ministry association, and surcharge selection may be submitted, while header or line times and Room selection cannot be changed. Room or time changes are handled manually until separately designed.
_Avoid_: changing Rooms without their time intervals, silently repricing a Confirmed Booking, treating Admin Booking edit as an unrestricted update

**Booking Draft**:
A standalone, non-locking snapshot of a member's proposed Booking lines (date, ministry, Title, lines), created when the member clicks Review & Confirm on the Timetable and addressed by an opaque id. It owns the required Booking Title from first creation through Draft read, Draft update, and final Booking confirmation. It never reserves the room — availability and price are recomputed live on every read, never cached on the Draft. Only its creator may view or edit it; edits PATCH the same Draft in place. Confirming an owned Draft consumes its Title onto the created Booking and deletes the Draft in the same request; an abandoned Draft is not otherwise cleaned up on a schedule. A member entering Start Booking deletes all of that member's Booking Drafts as an explicit action (every entry, not just a detected restart), independent of the (absent) expiry job. Distinct from a `facility.booking` row and from `BookingStatus.DRAFT`, which is unused today.
_Avoid_: a `facility.booking` row with status DRAFT, a slot hold or lock, a link shareable with non-creators, caching its quote or availability, treating the Start Booking cleanup as a scheduled expiry mechanism, a second browser-only Title at confirmation

**Recurring Series Draft**:
A standalone, non-locking snapshot of one weekly Recurring Booking Series proposal owned by a member: shared local time window, First occurrence, Last occurrence, weekday (implied by those dates), ministry context, ordered rooms, Title, permitted exclusions, and the current server quote plus payment-hold information. It is created from a preview-ready Repeated proposal, never reserves rooms, and is unavailable to every other member. Reads and confirmation revalidate current availability and policy; a stale proposal is non-confirmable and does not create a Series. Confirming an owned valid Draft atomically creates exactly one pending-payment Recurring Booking Series and consumes that Draft. Start Booking clears unconfirmed Recurring Series Drafts without deleting a created Series. Distinct from Booking Draft and from a Recurring Booking Series.
_Avoid_: widening Booking Draft to hold weekly-Series data, treating the Draft as a room hold, creating a Series from a consumed, missing, or another member's Draft, deleting a pending-payment Series when clearing Drafts

**System Setting**:
A generic, admin-editable key-value row (`namespace` + `setting_key` + typed `value`) for church-wide configuration, e.g. `facility.timezone` and the Booking line cap. Global only — no per-room or per-tenant scoping. Reads are cached and invalidated on admin edit.
_Avoid_: a per-room override table (that pattern was removed with Rental Policy Setting, ADR 0017), a feature-specific settings table

**Content File**:
A stored media object in the content library (metadata plus blob). Rooms bind to Content Files; they do not own uploads as a separate room-file type.
_Avoid_: attachment, asset, location file, inline URL as the bound object

**Product**:
A product line that owns its legal texts, identified by a built-in code. Operators do not invent Product codes; create picks from the built-in catalog only. This slice seeds `facility-booking` and `portal`, each with Terms of Service and Privacy Policy rows (bodies may start empty).
_Avoid_: App, Audience, git repo name as the identity, Operator-invented codes, seeding only one Product when both codes are required

**Legal Document**:
A living Markdown body for one Product and one Legal Document Kind, with locale translations. Saving replaces the current wording. Body is Markdown only (headings, lists, links); no embedded HTML and no images. It has a required **Effective Date** (a single calendar day when the current wording takes effect). Operators set Effective Date manually; saving body changes does not auto-change it. **Last Updated** is the audit `updated_at` instant, not Effective Date. Operators may soft-delete and restore under RBAC; there is no built-in hard block on delete. Soft-delete removes it from the public current set; restore brings the same row back. Create is allowed only for a built-in Product × Kind that has no row at all (including none in the recycle bin); if a soft-deleted row exists for that pair, create is rejected and the Operator must restore. There is no version history and no recorded acceptance. Distinct from Content File and from System Setting.
_Avoid_: ToS as the only document type, a single church-wide blob, HTML as the stored body, free-titled CMS pages, inline images, program-forbidden delete for built-in rows, creating a second active row while a soft-deleted twin exists, free-text Product codes, Effective from/to range as this field, treating Last Updated as Effective Date

**Effective Date**:
The single calendar day on which the Legal Document's current wording takes effect. Required. Stored and exchanged as a date (not a zoned instant). Distinct from Last Updated and from schedule Effective from / Effective to.
_Avoid_: datetime-with-timezone as the stored meaning, auto-bumping on every body save, optional empty Effective Date on an active document

**Last Updated**:
When the Legal Document row was last changed, from audit `updated_at`. It is not the legal Effective Date.
_Avoid_: showing Last Updated labeled as Effective Date, using Last Updated as the public "in force since" line

**Legal Document Kind**:
Which legal text a Legal Document is: Terms of Service or Privacy Policy. Identity is Kind plus Product code, not the display title. Both kinds ship for each seeded Product in this slice. Page/Footer titles come from client i18n by Kind, not from an editable title field.
_Avoid_: free-text type, title-as-key, treating Privacy Policy as another name for Terms of Service, deferring Privacy Policy to a later schema, Operator-edited display title as identity

**Terms of Service**:
The Legal Document Kind for the Product's terms of use.
_Avoid_: using Terms of Service to mean every legal page, acceptance log

**Privacy Policy**:
The Legal Document Kind for how the Product handles personal information. Same living, public-read, no-acceptance rules as Terms of Service.
_Avoid_: burying privacy copy inside Terms of Service, a separate acceptance workflow

**Public Legal Document read**:
Anyone may fetch the current Legal Document for a Product and Kind without signing in, via one read that takes Product code and Kind. Locale follows Accept-Language with fallback to the default locale. The payload includes the Markdown body for the resolved locale and the document Effective Date (calendar day). An empty body on an active row is still that document (200 + empty body). A soft-deleted or missing row is not found for the public read. Facility Booking's Product code is `facility-booking`; the Portal Product code is `portal`.
_Avoid_: requiring member JWT to read, treating empty body the same as soft-delete, one hard-coded route per Kind, locale query string as the v1 contract, omitting Effective Date from the public payload

**File association**:
The bind between one Content File and one resource (for example a Room). A Room gallery association is identified by resource kind `facility.room`, not by a class or table name. Binding or reordering a Room gallery is part of editing that Room. Putting a new file into the content library (including upload inside the Room picker) is a Content File upload. Deleting a Content File is allowed while associations exist: one confirmation lists every selected file's bound resources by name or code, including soft-deleted Rooms marked as deleted; then the files and all of their File associations are removed together. No orphan association rows remain. A gallery of ten images cannot accept another file; the picker is disabled and the server also rejects an over-cap save.
_Avoid_: blocking delete until unbind, leftover association rows after file delete, silent delete with no association warning, a count-only warning with no names, hiding soft-deleted Rooms from the warning, handler class names as resource kind, treating library upload as only a Room permission, toast for over-cap instead of blocking the picker

### Org / ministry

**Ministry**:
A church organizational unit with localized names, an optional ministry type, and a lifecycle status.
_Avoid_: MinistryType (catalog), treating a pending Ministry Application as already the same as an Active Ministry

**Ministry Application**:
A Ministry in the pending-approval lifecycle: the member has submitted it and it awaits a Ministry Approver decision. It is not a separate aggregate from the Ministry row.
_Avoid_: Application as a synonym for an Active Ministry, calling the approve/reject decision itself an Application

**Ministry Type**:
An optional catalog classification of a Ministry: Outreach, Internal, or Worship. A Ministry without a defined classification has no Ministry Type; it must not be silently classified as Internal.
_Avoid_: Ministry, free-text type on the Ministry row, using Internal as a fallback for an unspecified classification

**Active**:
The Ministry lifecycle status after approval. Booking and owned-ministry lists include Active Ministries.
_Avoid_: Approved as a Ministry status, using Approval status in place of Ministry status

**Ministry Approval**:
The decide outcome on a Ministry Application: approved or rejected. Approving moves the Ministry to Active.
_Avoid_: treating Approval as the Application itself, using Approval status as the Ministry's own status

**Ministry Approver**:
A person who may approve or reject a Ministry Application: the current incumbent of that Ministry's Owner position, or a user granted ministry approval authority in the admin portal.
_Avoid_: incumbent-only as the sole rule, RBAC-only as the sole rule

**Ministry Profile**:
A read-only member projection of one Ministry for its applicant, Ministry member, or current Owner-position incumbent. It returns localized name and Purpose with system-default fallback, lifecycle fields, Target Audiences, Priority Booking, Steward display information, and live Owner Position contact. It is not the approval decision resource.
_Avoid_: reusing approval detail as a general Profile, exposing all translations or admin audit identifiers, retaining a former Owner incumbent as current contact

**Application notification email**:
An Outlook message sent from a fixed system mailbox to the Owner-position incumbent when a member submits a Ministry Application. It deep-links into the facility-booking approval detail page after Microsoft sign-in. Body is bilingual: English first, then Chinese.
_Avoid_: applicant confirmation as the same email, using the incumbent's personal mailbox as the sender

**Application submit confirmation email**:
An Outlook message to the applicant right after submit, summarizing the Ministry Application and linking to My Ministry. Body is bilingual: English first, then Chinese.

**Application decision email**:
An Outlook message to the applicant when a Ministry Application is approved or rejected. When the Owner-position incumbent decides via the member approval flow, the message reflects an incumbent decision. When church staff decide via the admin portal, the message names the staff member and states that the decision was made on the incumbent's behalf (staff acting for the Owner-position approver). The staff approver is also recorded on the Ministry row (`approved_by_id` / `rejected_by_id`) for audit.
_Avoid_: treating this as the incumbent notification, using incumbent-only wording for a staff decision, exposing staff personal email in the body

**Incumbent staff-decision notification email**:
An Outlook message to the Owner-position incumbent when church staff approve or reject a Ministry Application via the admin portal. Names the staff member, states that staff acted on the incumbent's behalf, summarizes the outcome, and confirms no further action is required.
_Avoid_: treating this as the pending Application notification email, asking the incumbent to approve again after staff already decided

**Application summary (email)**:
A structured block in ministry application emails listing key facts about the Ministry Application (for example ministry type, applicant, submitted date). Distinct from the free-form rejection reason on decline.
_Avoid_: duplicating the full admin approval page, treating summary as a separate aggregate

**Assignable Owner position**:
An org position with `can_own_ministry` and a current incumbent. Booking create lists only these positions; submit is blocked if the chosen position has no incumbent.
_Avoid_: vacant positions in the create picker, submit without a recipient for incumbent notification

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
