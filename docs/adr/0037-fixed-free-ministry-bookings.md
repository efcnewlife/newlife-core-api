# Fixed free Ministry Bookings

## Status

Accepted. Core API pricing, lifecycle, and response contracts are implemented (EFC-271), as are post-creation association immutability (EFC-272) and the saved-record free flag (EFC-275). Frontend adoption (EFC-273, EFC-274) is tracked separately.

## Context and decision

Church Activity Bookings are entirely free, for Priority and Non-priority Ministries, One-time and Recurring alike. This replaces the Ministry percentage-discount policy in ADR 0029, including its treatment of surcharges: all room fees and surcharges are waived. Free quoting and creation do not require a configured Rental Rate.

Final confirmation creates a Confirmed Ministry Booking or a Confirmed Recurring Series with Confirmed Occurrences. Free Ministry Series have no pending-payment hold, payment-confirmation requirement, or payment-expiry cancellation. Personal Booking pricing and payment behavior remain unchanged.

We considered a System Setting toggle that restores charging through the existing Ministry Discount, but chose fixed free booking to avoid configurable pricing and lifecycle transitions. No charging toggle is introduced. The product has not launched, so legacy-data conversion and historical refunds are outside this change.

Existing Active Ministry and Booker stewardship eligibility, availability, opening-hours, Blackout, and Priority override rules still apply. Free pricing does not confer Priority override authority.

## Association and presentation

- Drafts may switch between Personal and Ministry contexts, or change Ministry, with server-side eligibility, availability, and pricing revalidation before confirmation.
- Once a Booking or Series has been created, its Ministry association is immutable, including through Admin edits. Switching Personal to Ministry, Ministry to Personal, or one Ministry to another requires cancellation and a new booking. This replaces ADR 0029's editable Admin Ministry association while preserving its price-snapshot boundary.
- Member and Admin views identify the booking as a free Ministry Booking and show zero charges and a zero total. Do not show a Ministry percentage discount or payment prompts.
- Surcharge functionality has not been implemented or opened to users. This change does not introduce surcharge selection, service-selection persistence, or fulfillment workflows. The policy still requires Ministry surcharge amounts to be zero; dormant catalog or input scaffolding must not introduce a charge.

## Implementation acceptance boundaries

- Availability quotes, line previews, aggregate quotes, Drafts, Series conflict previews, and final creation must agree on free Ministry pricing. Enforce the policy on the server for both member and Admin on-behalf creation.
- The Ministry Discount must not affect Ministry quotes, even if its catalog rule is edited, absent, or inactive. Personal Recurring Discount behavior remains unchanged.
- Free Ministry Series and Occurrences must not enter payment queues, expose payment instructions, send payment-request messages, or be cancelled by payment expiry. Normal confirmation and override notifications retain their existing purposes.
- Financial snapshots must represent zero payable room fees and surcharge charges without fabricating a Rental Rate when none exists.
- No legacy-data conversion, historical refund workflow, or charging toggle is required.

## API contract (EFC-271)

The server decides free pricing; a client never derives it from `ministryId` alone. "Eligible" means the existing Active Ministry plus current primary/secondary Booker stewardship check. An ineligible Ministry proposal is still rejected by quote/create gates exactly as before.

- `isFreeMinistry` (boolean, default `false`) is present on: member and Admin preview quotes, member and Admin discount eligibility, Booking Draft detail, member and Admin Recurring conflict preview, and Recurring Series Draft detail.
- Free quote totals: `subtotalAmount`, `discountAmount`, `surchargeAmount`, `quotedAmount` are `0.00`; `discountPercent` is `0`; `discountCode` is `null`. Dormant `surcharge_codes` are ignored, not priced or validated.
- Free quote `roomLines`: one entry per requested room line, in request order, with the real `facilityId` and `billedHours`, `currency` from the request, `lineSubtotal` `0.00`, `isDefault` `false`, and `rentalRateName`, `billingUnit`, `unitAmount`, `applicability` all `null`. No Rental Rate is resolved, so a Room without one still quotes. Personal lines are unchanged and still fail with "No active rental rate" when none applies.
- Recurring Series Draft detail: `pendingPaymentHoldDays` and `paymentHoldExpiresAt` are `null` for every Ministry proposal (including one that is not currently confirmable) and keep their existing non-null values for Personal proposals. Ministry evaluation never reads the hold-days setting.
- Created Ministry Series: `status` `confirmed`, `paymentHoldExpiresAt` `null`, every occurrence `confirmed`. Created One-time Ministry Booking stays `confirmed`. Persisted snapshots store zero amounts, `is_mission_aligned = true`, and null rate fields on room rows. Payment queues, the expiry sweep, and payment instructions already key off `pending_payment`, so free Ministry bookings never appear in them.
- No database shape change is required; every affected snapshot column is already nullable.

## API contract (EFC-272)

`PUT /admin/api/v1/facility/bookings/{id}` is the only post-creation surface that accepts a Ministry association; it applies to One-time Bookings and Recurring Occurrences alike. Member title edits for Bookings and Series accept only `title`. No Series-level edit API exists.

- `ministry_id` omitted: the stored association is kept.
- `ministry_id` equal to the stored value (including `null` on a Personal Booking): accepted. The title is saved; eligibility is not re-checked and the Booking is not repriced.
- `ministry_id` different from the stored value (Personal to Ministry, explicit `null` on a Ministry Booking, or another Ministry): `409` with `error_code` `FACILITY_BOOKING_MINISTRY_ASSOCIATION_LOCKED`. Nothing is written, including the title. The client should direct the operator to cancel and create a new booking.
- Booking and Series Drafts are unaffected; their association stays editable with live revalidation.

## API contract (EFC-275)

Saved records state whether they were created as free Ministry bookings, so clients no longer infer it from `ministryId` plus a zero `quotedAmount`.

- `isFreeMinistry` (boolean, default `false`) is present on: member Booking detail (`MemberBookingDetail`, One-time and Recurring Occurrences, including the title-edit response), member Recurring Series detail and its `occurrences`, the member Series create response, Admin Booking detail, and Admin Recurring Series detail and its `occurrences`. Each Occurrence reports its own snapshot.
- The value is read from the persisted `is_mission_aligned` snapshot of that Booking or Series, which creation sets only for free Ministry pricing since EFC-271. Rows created earlier under the ADR 0029 Ministry Discount also carry `true`; they are pre-launch data covered by "no legacy-data conversion" and must be reset rather than relied on. The flag never re-evaluates current Ministry status or Booker stewardship, so it stays stable after a Booker loses stewardship or a Ministry is deactivated.
- Personal records and any Ministry record not created as free return `false`.
- Admin Booking list and range items do not carry the flag. Admin Booking detail keeps `isMissionAligned` for compatibility; clients should read `isFreeMinistry`.

## Remaining implementation gaps

- Member and Admin presentation, payment actions, and discount eligibility displays require coordinated review. Backend zero totals alone do not satisfy the free-booking experience. Frontends should switch from the 30% Ministry discount display to `isFreeMinistry`.

## Related

- [EFC-270](https://linear.app/jayhsia/issue/EFC-270/spec-fixed-free-ministry-bookings) / [Core API specification #249](https://github.com/efcnewlife/newlife-core-api/issues/249).
- ADR 0017 (rental quoting), ADR 0019 (Recurring Booking Series), ADR 0029 (Booking Discounts), ADR 0030 (payment holds).
