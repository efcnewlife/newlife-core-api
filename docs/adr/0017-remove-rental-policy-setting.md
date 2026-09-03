# 0017. Remove FacilityRentalPolicySetting; quote from rates only

## Status

Accepted

## Context

Rental quoting mixed three catalogs: Rental Rate Template (and Room bindings), Discount / Surcharge rules, and `FacilityRentalPolicySetting` (minimum fees, max rooms, unused daily-flat threshold). Product direction is to price from **Rental Rate Template** selection only for rate lines, keep Discount / Surcharge as today, and **drop Policy Setting entirely** — including the minimum-fee floor on `quoted_amount`.

ADR 0015 still described the 1–3 Booking line cap as coming from `MAX_ROOMS_PER_BOOKING` policy. That coupling is removed with the Policy Setting aggregate.

## Decision

- Delete the **Rental Policy Setting** concept end-to-end (model, keys, admin API, seed, tests, and any admin UI that only exists for it). Schema drop is a human-owned Alembic migration.
- **Preview quote / booking quote**: `quoted_amount = sum(line subtotals) − discount + surcharges`. No minimum-fee floor. Primary facility is not used to look up a fee floor.
- **Discount / Surcharge**: unchanged (mission-aligned preferred over recurring; surcharges only when requested via `surcharge_codes`).
- **Booking line cap**: still **1–3** Booking lines as a hard product rule (serializers / constants), not a Policy Setting row. This supersedes ADR 0015’s wording that the cap is read from `MAX_ROOMS_PER_BOOKING` policy.

## Considered options

- Temporarily ignore Policy Setting in `PricingService` but keep the table and admin CRUD — rejected; leaves a dead catalog and reopens “why is this unused?”
- Soft-disable only `minimum_fee_*` while keeping max-rooms policy — rejected; the decision is to remove the whole Policy Setting slice.

## Consequences

- Implementers must stop reading Policy Setting in quote and booking validation; wire the 1–3 line cap without that table.
- Human Alembic follow-up (not this change set): drop `facility.rental_policy_setting` and related indexes/constraints. Do not add a revision under `alembic/versions/`.
- `newlife-portal-frontend` policy-settings API client (and any UI) becomes obsolete with the admin routes.
- Facility rental docs / QA that list seed minimum fees or policy CRUD need a follow-up edit outside this ADR file.
- Reintroducing a fee floor later is a new decision, not flipping a dormant Policy Setting feature.

## Related

- ADR 0015 (line cap remains; policy-backed source superseded)
- ADR 0016 (member preview-quote shape unchanged by this decision)
