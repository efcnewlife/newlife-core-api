# Fixed free Ministry Bookings

## Status

Accepted. This document describes the intended policy, not completed implementation.

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

## Implementation gaps identified during review

These are implementation requirements derived from the policy, not completed work:

- Recurring proposal and Draft results currently require payment-hold fields. Free Ministry results must represent the absence of a hold consistently through API serializers and frontend consumers, rather than inventing a deadline.
- Quote line results currently require billing-unit and amount fields and pricing resolves a rate before discounts. The no-rate Ministry path must support every consumer without presenting an invented catalog rate.
- Admin forms may submit an unchanged Ministry association on every save. Immutability must reject association changes while allowing an unchanged submitted value, so ordinary title edits remain possible.
- Member and Admin presentation, payment actions, and discount eligibility displays require coordinated review. Backend zero totals alone do not satisfy the free-booking experience.

## Related

- [EFC-270](https://linear.app/jayhsia/issue/EFC-270/spec-fixed-free-ministry-bookings) / [Core API specification #249](https://github.com/efcnewlife/newlife-core-api/issues/249).
- ADR 0017 (rental quoting), ADR 0019 (Recurring Booking Series), ADR 0029 (Booking Discounts), ADR 0030 (payment holds).
