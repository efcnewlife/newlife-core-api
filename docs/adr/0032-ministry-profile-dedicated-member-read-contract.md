# Ministry Profile has a dedicated member read contract

## Status

Accepted

## Context

Facility Booking needs a read-only Ministry Profile for applicants, Ministry members, and the current Owner-position incumbent across Active, Pending approval, and Rejected lifecycle states. The existing member approval detail resource is a decision flow and is not an appropriate general Profile.

## Decision

Expose `GET /api/v1/ministry/ministries/mine/{ministryId}` as a dedicated member Profile endpoint authorized by the same per-Ministry relationships as approval detail (applicant, Ministry member, or current Owner-position incumbent). Return a purpose-built projection: localized name and Purpose with system-default locale fallback, status and lifecycle dates, rejection reason when applicable, Target Audiences, Priority Booking, Steward display information (no internal user ids), and localized Owner Position with nullable live incumbent display name/email. Resolve Owner contact at read time so a vacant position exposes no incumbent and a former incumbent is not shown. Do not return all translations or admin audit fields. No schema migration.

## Consequences

- `MinistryApprovalService.get_ministry_profile` owns authorization and projection mapping; delivery uses `ApiMinistryProfile`.
- Approval detail and Profile remain separate contracts; Profile stays read-only.
- Application-service tests cover authorized relationships, denial, locale fallback, lifecycle fields, live Owner contact, and vacancy.
