# Member mock login for Facility Booking QA (dev/staging only)

Facility Booking QA needs passwordless member sign-in without Microsoft Entra ID, with **real** JWTs and per-account ministry/booking authorization — not a frontend fake session. We add `POST /api/v1/auth/mock-login` (`{ email }`, snake_case) on the member app surface. It is enabled only when `MOCK_LOGIN_ENABLED=true` (non-production deployments). The email must end with the configured testing suffix (default `@test.local` via `TESTING_ACCOUNT_EMAIL_SUFFIX`). The user must already exist in `auth.user`, be `verified` and `is_active`. Request Origin must resolve to a registered member web app (`MEMBER_WEB_APPS`). Staging also requires header `X-Mock-Login-Secret` matching `MOCK_LOGIN_SECRET`. On success we reuse `LoginService.complete_member_login` (same token shape as `/auth/login/microsoft`). Failed suffix, missing user, disabled feature, bad Origin, or bad secret all return generic `401` (no account enumeration). Testing accounts are provisioned by operator CLI only ([#118](https://github.com/efcnewlife/newlife-core-api/issues/118)); no `is_testing_account` column. Product context and frontend consequences: [`efcnewlife/facility-booking-frontend` ADR 0021](https://github.com/efcnewlife/facility-booking-frontend/blob/main/docs/adr/0021-mock-login.md).

## Considered Options

- **`is_testing_account` on `auth.user`** — rejected: `@test.local` suffix is sufficient; avoids migration and Admin UI; trade-off is testing emails cannot use production-looking domains.
- **Separate login service path with elevated scopes** — rejected: mock login must exercise the same member authorization as Microsoft login.
- **Production mock login with IP allowlist** — rejected: dev and staging only.
- **`POST /api/v1/auth/login/testing`** — rejected: `/mock-login` matches product language (facility-booking ADR 0021).

## Consequences

- New settings: `MOCK_LOGIN_ENABLED`, `MOCK_LOGIN_SECRET`, `TESTING_ACCOUNT_EMAIL_SUFFIX`; document in `example.env`.
- New application service (or method on existing auth service), delivery route under `portal/routers/apis/v1/auth.py`, request serializer, mapper to a small command.
- No Alembic migration in the mock-login slice (suffix-only identification).
- CLI `create-mock-user` tracked separately in #118; must enforce `@test.local` (or configured suffix).
- Audit: log mock-login attempts (success and failure) at application level when implementing.
- Persona/ministry relationship seeding for `@test.local` users is out of scope — follow-up ticket.
