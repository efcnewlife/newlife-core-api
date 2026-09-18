# Managed non-stacking Booking Discounts

## Status

Accepted

## Context

Facility rental has two business discounts: Active Ministry Bookings receive 30% and Recurring Bookings receive 20%. The system must retain the published commercial amount after confirmation while allowing authorized administrators to manage future discount percentages.

## Decision

- Keep the Ministry Discount and Recurring Discount as separately managed Rental Discount Rule catalog values, seeded at 30% and 20% respectively.
- An Active Ministry Booking receives the Ministry Discount only when its Booker is a current primary or secondary Ministry member. Otherwise, a Recurring Booking receives the Recurring Discount. Discounts never stack.
- Expose one generic Booking Discount Eligibility contract for both one-time and Recurring proposals. It resolves `discount_code` and `discount_percent` from booking type, Ministry, and Booker; a quote or create request still re-evaluates eligibility. Do not accept a client-controlled `is_mission_aligned` input.
- Apply the selected percentage only to the sum of room-line subtotals; add surcharges after the discount.
- A managed Discount Rule accepts a percentage from 0 to 100 with at most two decimal places. An inactive or absent rule gives no discount.
- Calculate or recalculate a quote only before confirmation. When a Booking or Series becomes Confirmed, persist its financial snapshots and never reprice them because a rate or discount rule changes later. A Pending-payment Recurring Booking Series locks its quoted amount on creation; payment confirmation only changes lifecycle status.
- The Admin Booking edit form displays time fields as disabled. Its existing `PUT /admin/api/v1/facility/bookings/{id}` removes top-level and per-room time inputs, adds title, and retains Ministry association and surcharge selection. It does not allow Room changes; Room or time changes are handled manually until separately designed. Booker and authorized Administrator title edits never reprice the Booking.

## Consequences

- A 30% Ministry Discount is not a client-controlled `is_mission_aligned` assertion.
- Changing a Discount Rule affects only future or still-unconfirmed quotes.
- Booking update and payment-confirmation flows must respect the confirmed-price boundary.
