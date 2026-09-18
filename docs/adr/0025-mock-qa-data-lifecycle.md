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
- The existing Graph Entra application (`AZURE_APP_CLIENT_ID`) uses site-scoped `Sites.Selected` plus an explicit write grant for the supplied archive site. Upload failure leaves committed data and local CSVs intact, reports failure, and exits nonzero.

## `seed-mock-data`

Reads the single local account/Ministry CSV pair for the current environment (fails if missing or ambiguous — retention keeps only one pair per env locally) and completes the scenarios `seed-mock-users` cannot: a personal Rental Booking for the `personal` Mock user, activation of the `steward` Mock user's draft Ministry plus a Church Activity Booking on it, assignment of the `owner` Mock user as the incumbent of the first active `can_own_ministry` Position, and a second, pending Ministry Application (submitted by the `steward` Mock user) owned by that same Position so it appears in the new incumbent's approval queue. All writes are one transaction. It re-runs the same dev/staging guard as `seed-mock-users` and fails clearly (naming the missing prerequisite command) when the inventory, the steward Ministry is not still in `draft`, no active Room, or no `can_own_ministry` Position exists.

## `remove-mock-data`

Hard-deletes every `@test.local` account and everything it derived: profiles, tokens, Bookings, Recurring Booking Series, Booking Drafts, Ministries, and steward/position relationships. A Ministry is a removal candidate when at least one Mock user is a member; before deleting anything, the command checks every candidate for a non-Mock-user member, Booking, Recurring Booking Series, Booking Draft, or Ministry Approval decision (requester or resolver), and fails naming the offending Ministry rather than guessing whether it is safe to remove — a real person's Ministry membership, Booking, or approval decision is never silently orphaned. Catalog data (locales, RBAC, positions, rooms, rates, system settings, Legal Documents, Ministry Types) and the local/SharePoint CSV archives are never touched: cleanup and archive retention are unrelated concerns. It re-runs the same dev/staging guard as `seed-mock-users` / `seed-mock-data`, and is a no-op (nothing deleted, exit 0) when no `@test.local` account exists.

## SharePoint archive-writer provisioning (`seed-mock-users`)

Non-secret configuration (`portal/config.py`, `example.env`): `SHAREPOINT_SITE_ID`, `SHAREPOINT_DRIVE_ID`, `SHAREPOINT_TEST_ACCOUNT_FOLDER`. Auth reuses `AZURE_TENANT_ID`, `AZURE_APP_CLIENT_ID`, and `AZURE_APP_CLIENT_SECRET` (same Graph app as directory sync and mail). That secret is never written to CSVs, logs, or this document. Set `SHAREPOINT_TEST_ACCOUNT_FOLDER` per environment when the archive path differs.

Manual provisioning steps (tenant/site administrator, one time per tenant):

1. Reuse the existing Entra app (`AZURE_APP_CLIENT_ID` / `AZURE_APP_CLIENT_SECRET`) — the same registration used for directory sync and Graph mail. Do not create a second app.
2. Grant it the Microsoft Graph **application** permission `Sites.Selected` and complete tenant admin consent. Do not grant `Sites.ReadWrite.All` or any other tenant-wide Sites permission.
3. Resolve the target SharePoint site's id (`GET /sites/{hostname}:/{site-path}`) and its document library drive id (`GET /sites/{site-id}/drive`); record them as `SHAREPOINT_SITE_ID` / `SHAREPOINT_DRIVE_ID`. The archive site is `https://efcnewlifegospelchurch.sharepoint.com/sites/EFCNewlifeTech-FacilityBookingSystem`.
4. Grant the app `write` access to that one site only: `POST /sites/{site-id}/permissions` with the app's client id and role `write` (equivalently, PnP PowerShell `Grant-PnPAzureADAppSitePermission -Site {url} -AppId {client-id} -Permissions Write`). This is the explicit resource-specific grant `Sites.Selected` requires beyond admin consent.
5. Confirm the site's document library already has the configured folder (default `Testing Account`, or the `SHAREPOINT_TEST_ACCOUNT_FOLDER` value for that environment). Archive folder: [EFCNewlifeTech-FacilityBookingSystem Shared Documents / Testing Account](https://efcnewlifegospelchurch.sharepoint.com/sites/EFCNewlifeTech-FacilityBookingSystem/Shared%20Documents/Forms/AllItems.aspx?id=%2Fsites%2FEFCNewlifeTech%2DFacilityBookingSystem%2FShared%20Documents%2FTesting%20Account&viewid=1d38832a%2D0673%2D47a3%2D8385%2Dc23cfd485edd).

Manual verification (after provisioning, before relying on the archive in an environment): run `seed-mock-users` (with `--force` in `stg`) against that environment and confirm both CSVs appear under `SHAREPOINT_TEST_ACCOUNT_FOLDER` in SharePoint with the exact `YYYY-MM-DD_HHMM_<env>_*.csv` names, and that the app cannot enumerate or write to any other SharePoint site.
