# Portal CLI

This document describes every command registered by `portal.cli.main`.

Run commands from the repository root:

```bash
uv run python -m portal.cli.main <command>
```

Show the registered commands or the options for one command:

```bash
uv run python -m portal.cli.main --help
uv run python -m portal.cli.main <command> --help
```

## Prerequisites

Before commands that read or write the database:

1. Configure `.env`.
2. Start the local services with `docker compose up -d` when running locally.
3. Apply the human-managed database migrations with `uv run alembic upgrade head`.

`init-all` and individual catalog seed commands require a reachable database. `seed-mock-users` also requires its SharePoint archive-writer settings; see `example.env` for the `SHAREPOINT_*` variables.

## Environment guards

Most business/demo commands run in `dev` by default. For the commands marked **Force outside dev**, `--force` both skips the confirmation prompt and permits the command when `ENV` is `stg` or `prod`.

Mock QA lifecycle commands use a stricter policy:

| Environment | `seed-mock-users` | `seed-mock-data` | `remove-mock-data` |
| --- | --- | --- | --- |
| `dev` | Allowed; asks for confirmation unless `--force` is supplied. | Allowed; asks for confirmation unless `--force` is supplied. | Allowed; asks for confirmation unless `--force` is supplied. |
| `stg` | Requires `--force`. | Requires `--force`. | Requires `--force`. |
| `prod` | Rejected, even with `--force`. | Rejected, even with `--force`. | Rejected, even with `--force`. |

## Bootstrap and catalog commands

| Command | Purpose | Notes |
| --- | --- | --- |
| `init-all` | Bootstrap the catalog and then create a superuser interactively. | Runs locales, RBAC, system settings, positions, target audiences, facility rooms/rates, Legal Documents, then `create-superuser`. It is fail-fast and does not seed Ministry Types or business/demo data. |
| `create-superuser` | Create an admin superuser through interactive prompts. | Use after a catalog exists if `init-all` was not used. |
| `init-locales` | Insert supported system locales. | Run before `init-rbac` when executing catalog steps individually. |
| `init-rbac` | Upsert verbs, resources, permissions, roles, and role-permission mappings. | Safe to re-run. |
| `reset-rbac --force` | Delete all RBAC data and seed it again. | **Destructive.** Deletes verbs, resources, permissions, roles, translations, mappings, and user-role assignments. **Force outside dev.** |
| `seed-system-settings` | Insert missing built-in system settings. | Never overwrites existing values. |
| `seed-legal-documents` | Insert missing built-in Legal Documents. | Never overwrites existing Product x Kind pairs. |
| `seed-positions [--force]` | Upsert organization positions and translations. | **Force outside dev.** |
| `seed-ministry-types [--force]` | Upsert Ministry Type catalog rows and translations. | Not included in `init-all`. **Force outside dev.** |
| `seed-target-audiences [--force]` | Upsert target-audience catalog rows and translations. | **Force outside dev.** |
| `seed-facility-rental [--force]` | Upsert rooms, rates, discounts, and surcharges. | **Force outside dev.** |
| `seed-facility-rental [--force] --reset` | Clear Facility rental/booking seed data and rebuild the facility catalog. | **Destructive.** Deletes bookings, blackouts, slot templates, rooms, rates, discounts, and surcharges before reseeding. **Force outside dev.** |

## Local demo commands

| Command | Purpose | Notes |
| --- | --- | --- |
| `seed-local-demo [--force]` | Seed demo Ministries, slot templates, blackouts, and Bookings. | Requires catalog prerequisites including rooms, Ministry Types, audiences, and owning positions. It replaces only seed-prefixed demo data and preserves unrelated admin-created rows. **Force outside dev.** |
| `seed-position-assignments [--force]` | Assign configured users to positions as incumbents. | Uses the seed data's email and position-code mappings. **Force outside dev.** |

Recommended local demo flow:

```bash
uv run python -m portal.cli.main init-all
uv run python -m portal.cli.main seed-ministry-types
uv run python -m portal.cli.main seed-local-demo
```

## Mock QA lifecycle commands

| Command | Purpose | Prerequisites and outcomes |
| --- | --- | --- |
| `seed-mock-users [--force]` | Create the complete Mock inventory: five `personal`, three `steward`, one `owner`, and one inactive `@test.local` Testing accounts plus ten scheduled Mock Ministries; generate the account and Ministry CSV inventory. | Requires a catalog locale and configured SharePoint archive writer. The CSV pair is retained locally and uploaded to the configured `Testing Account/<env>` SharePoint folder. A new run is rejected while an active Mock snapshot exists; run `remove-mock-data` first. |
| `seed-mock-data [--force]` | Complete the near-term Facility Booking fixture suite for the current Mock inventory. | Requires exactly one current local inventory pair produced by `seed-mock-users`, catalog rooms, and an active owner-capable Position. Creates weekly slot templates, campus-wide and room-specific Blackouts, ten confirmed Bookings (six personal, four Ministry, including one multi-room), assigns the owner Mock user, and creates a pending Ministry Application. Does not create accounts or inventory Ministries. Booking placement searches the next 30 days and fails atomically when a complete suite cannot be placed. |
| `remove-mock-data [--force] [--include-legacy-demo]` | Permanently delete all `@test.local` Mock users, their derived QA data, and current `mock:`-marked slot templates and Blackouts. | Removes profiles, tokens, Bookings, recurring series, drafts, Ministries, Mock steward/position relationships, and marker-owned non-user fixtures. Preserves catalog data and both local and SharePoint CSV archives. Fails before deleting anything if a candidate Ministry has a non-Mock dependency. `--include-legacy-demo` also removes only the exact known `seed.*@local.test` Demo accounts and `seed:`-marked fixtures; a non-legacy dependency fails the whole run. The transition flag uses the same Mock lifecycle environment guard. |

Recommended Mock QA flow:

```bash
# Initial catalog bootstrap
uv run python -m portal.cli.main init-all

# Create a fresh inventory and archive it locally and in SharePoint
uv run python -m portal.cli.main seed-mock-users

# Add near-term Booking, Blackout, slot-template, and approval fixtures for that inventory
uv run python -m portal.cli.main seed-mock-data

# Remove all generated Mock QA data when finished
uv run python -m portal.cli.main remove-mock-data

# Optional transition: also remove exact known legacy Demo accounts and seed: markers
uv run python -m portal.cli.main remove-mock-data --include-legacy-demo
```

For staging, use `--force` with every Mock QA lifecycle command:

```bash
uv run python -m portal.cli.main seed-mock-users --force
uv run python -m portal.cli.main seed-mock-data --force
uv run python -m portal.cli.main remove-mock-data --force
uv run python -m portal.cli.main remove-mock-data --force --include-legacy-demo
```

## Microsoft Entra user synchronization

| Command | Purpose | Notes |
| --- | --- | --- |
| `sync-microsoft-users [--dry-run] [--force] [--filter "<OData filter>"]` | Sync `@efcnewlife.org` Entra Member users into auth tables. | Requires the general Microsoft Graph configuration (`AZURE_TENANT_ID`, `AZURE_APP_CLIENT_ID`, and `AZURE_APP_CLIENT_SECRET`), not the dedicated SharePoint archive writer credentials. **Force outside dev.** |
| `sync-microsoft-users --dry-run` | Preview create, update, and link results without database writes. | Use before a write-mode synchronization. |
| `sync-microsoft-users --filter "<OData filter>"` | Override the default Microsoft Graph `/users` OData filter. | Use only with a valid Microsoft Graph filter expression. |

## Safety notes

- Review the confirmation prompt before continuing. `--force` skips it.
- Use `--force` for staging only when the operation and target environment have been confirmed.
- Do not run `reset-rbac` or `seed-facility-rental --reset` casually; both remove material data.
- Mock QA data must stay limited to `@test.local`. Use `remove-mock-data` rather than manually deleting generated records.
