# Ministry Application notifications via Graph and incumbent-only member approval

When a member submits a **Ministry Application** from Facility Booking, the Owner-position **incumbent** must be notified and able to decide without opening the admin portal. We send three bilingual Outlook messages (English block first, then Chinese in the same body) from a **fixed system mailbox** via Microsoft Graph `Mail.Send` (application permission). Recipients: incumbent notification with a Facility Booking deep link; applicant submit confirmation with ministry summary and My Ministry link; applicant decision email on approve/reject.

Member `/api/v1` approval endpoints are **incumbent-only** (including self-approve when the applicant is the incumbent). Admin portal approve/reject stays **RBAC-only** (`ministry:approval`) and is unchanged in this slice — two surfaces, two authorization rules.

Assignable Owner positions for create must have a **current incumbent**; submit is blocked otherwise so every Application has an email recipient.

## Considered Options

- **Incumbent-only everywhere (including portal)** — rejected for this slice: slows E2E; portal Approvals queue already works for staff.
- **RBAC-only on booking** — rejected: product wants incumbent action from email deep link in the member SPA.
- **Separate Ministry Application aggregate** — rejected: Application is a pending Ministry lifecycle state; avoids duplicate rows and matches existing `OrgMinistry` + `OrgMinistryApproval`.
- **Single-language email by recipient locale** — rejected: church policy is bilingual EN+ZH in one message (Canada-style stacking).
- **Email invite for secondary stewards without `auth.user`** — rejected: roster requires existing users; member user search picks secondaries.

## Consequences

- New Graph mail provider (send only), env for system mailbox and Facility Booking base URL for links.
- New member APIs: steward user search, pending-for-me approvals, incumbent approve/reject, resubmit on rejected; extend create application with ministry type and optional target audiences.
- `list_assignable` filters to positions with incumbents.
- Tests extend `MinistryApprovalService` stubs; mail is asserted via a port/fake, not live Graph.
- Entra app registration needs `Mail.Send` application permission and admin consent.
