# 0031. Booking Draft owns required Title

## Status

Accepted

## Context

ADR 0018 stored only date, ministry, and lines on a Booking Draft. The member Timetable now collects the required Booking Title before Review & Confirm, and Booking Details must reload that Title from the Draft rather than from a second browser-only field. Recurring Series Draft already persisted Title; One-time Booking Draft did not.

## Decision

- Persist a required, trimmed 1-30-character plain-text Title on `facility.booking_draft`, using the same `BookingTitle` rule as Booking.
- Member create and update Draft requests require Title at the API boundary. Draft read returns that Title.
- Member Booking confirmation from an owned Draft consumes the Draft-owned Title. The confirm request may omit Title; a leftover request Title must not override the Draft.
- Direct create without an owned Draft still requires Title on the create command.
- The Alembic revision that adds the column is human-owned.

## Consequences

- ADR 0018's stored-fields sentence is superseded for Title only. Draft remains non-locking and owner-scoped.
- Existing Draft rows need a human migration backfill before `title` can be NOT NULL.

## Related

- ADR 0018 (Booking Draft)
- ADR 0028 (Recurring Series Draft checkout)
- facility-booking-frontend#133
