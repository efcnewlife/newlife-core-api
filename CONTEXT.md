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
The booking's main room id used for list filters (`facility_id` / list `facilityId`). For multi-line bookings this is the lowest `sequence` line's `facility_id` (first cart line), not the only room on the booking.
_Avoid_: room (ambiguous when multiple), main room (synonym drift), treating Primary facility as the only room shown on Booking Grid, assuming one `booking_room` row per room

**Booking line**:
One room interval on a booking: `facility_id`, `start_at`, `end_at`, and `sequence`. A booking has 1-3 lines. The same room may appear on more than one line with different intervals on the same local calendar day. Distinct from Primary facility and from the booking header envelope.
_Avoid_: room (when meaning a line), cart item without times, assuming one row per room in `booking_room`

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
A room-closed interval that makes the room unbookable. Overlap with a Blackout is a distinct rejection from a Scheduling Conflict; the client must show a different prompt.
_Avoid_: scheduling conflict, "closed" without naming the Blackout rule

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
A church organizational unit with localized names, a ministry type, and a lifecycle status.
_Avoid_: MinistryType (catalog), treating a pending Ministry Application as already the same as an Active Ministry

**Ministry Application**:
A Ministry in the pending-approval lifecycle: the member has submitted it and it awaits a Ministry Approver decision. It is not a separate aggregate from the Ministry row.
_Avoid_: Application as a synonym for an Active Ministry, calling the approve/reject decision itself an Application

**Ministry Type**:
A catalog classification of a Ministry: Outreach, Internal, or Worship.
_Avoid_: Ministry, free-text type on the Ministry row

**Active**:
The Ministry lifecycle status after approval. Booking and owned-ministry lists include Active Ministries.
_Avoid_: Approved as a Ministry status, using Approval status in place of Ministry status

**Ministry Approval**:
The decide outcome on a Ministry Application: approved or rejected. Approving moves the Ministry to Active.
_Avoid_: treating Approval as the Application itself, using Approval status as the Ministry's own status

**Ministry Approver**:
A person who may approve or reject a Ministry Application: the current incumbent of that Ministry's Owner position, or a user granted ministry approval authority in the admin portal.
_Avoid_: incumbent-only as the sole rule, RBAC-only as the sole rule

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
