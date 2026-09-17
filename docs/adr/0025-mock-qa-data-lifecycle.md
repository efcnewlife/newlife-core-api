# Mock QA data lifecycle and SharePoint inventory archive

Mock login needs more than a single manually entered account to exercise real Facility Booking authorization, personal bookings, Ministry bookings, and approval. We separate bootstrap catalog data from random Mock business data: `init-all` initializes catalog data and an interactive superuser, `seed-mock-data` and `seed-mock-users` create random `@test.local` Mock users and their scoped scenarios, and `remove-mock-data` removes all Mock-user-derived data while preserving catalog data. Each seed writes the current environment's account and Ministry inventory locally and archives the pair in the designated SharePoint environment folder.

## Considered Options

- **Reuse `seed-local-demo` identities** — rejected: its `@local.test` users cannot satisfy the Mock login testing-account suffix gate.
- **Use fixed, idempotent Mock users** — rejected: every seed must create a fresh random QA dataset, with the CSV inventory as the source of the current identities.
- **Automatically clear Mock data before every seed** — rejected: creation must not conceal a destructive operation, especially in staging.
- **Delete all data during Mock cleanup** — rejected: locales, RBAC, positions, rooms, rates, system settings, Legal Documents, and other catalog data are environment foundations.
- **Use tenant-wide SharePoint permissions or local files only** — rejected: archives must be retained remotely, but the uploader must be isolated to the intended SharePoint site.

## Consequences

- Mock data lifecycle commands are available only in `dev` and `stg`; staging requires `--force`, and production is always rejected.
- Ministries created by the Mock data lifecycle omit Ministry Type and require the optional-Ministry-Type schema revision to be applied.
- Cleanup deletes every `@test.local` account and its derived data, but fails rather than guessing when a candidate Ministry also has non-Mock-user dependencies.
- Same-minute CSV name collisions are errors; local output retains only the latest pair per environment, while SharePoint retains all historical pairs.
- A dedicated app-only Microsoft Entra application uses site-scoped `Sites.Selected` plus an explicit write grant for the supplied archive site. Upload failure leaves committed data and local CSVs intact, reports failure, and exits nonzero.
