---
name: alembic-check
description: >-
  Checks whether local Alembic revision heads match the database alembic_version
  state (read-only). Use when the user asks if migrations are up to date, whether
  the DB is at head, Alembic current vs heads, or migration sync status. Never
  runs upgrade, downgrade, revision, stamp, or edits alembic/ files.
---

# Alembic Check (read-only)

Verify that the database revision matches the project's Alembic head(s).
**Check only — never migrate or create revisions.**

## Hard rules

- Do **not** run: `upgrade`, `downgrade`, `revision`, `stamp`, `merge`
- Do **not** add, modify, or delete anything under `alembic/`
- Do **not** run `alembic check` (that compares models to DB schema, not version sync)
- Run all commands with uv from the repo root: `uv run alembic …`
- Report status only; if behind, tell the user a human must run migrations

## Workflow

Run from the project root (`newlife-core-api`):

```bash
uv run alembic current
uv run alembic heads
```

Optional context (still read-only):

```bash
uv run alembic history -r current:head
```

### Interpret results

| Situation | Verdict |
|-----------|---------|
| `current` revision ID(s) equal `heads` revision ID(s) | **UP TO DATE** |
| `current` is empty / no row / cannot connect | **UNKNOWN** — DB unreachable or never migrated |
| `current` is an ancestor of `heads` (history shows pending steps) | **BEHIND** |
| Multiple `heads` (branched) | **BRANCHED** — human must resolve before upgrade |
| `current` not in local history | **DIVERGED** — DB revision missing from this checkout |

`(head)` markers on `alembic current` output also indicate the DB is already at a head.

## Report format

Reply with a short status block:

```text
Alembic sync: <UP TO DATE | BEHIND | BRANCHED | DIVERGED | UNKNOWN>
DB current:   <revision or "(none)">
Local heads:  <revision(s)>
Pending:      <none | list revision ids / summary from history>
Action:       <none | ask a human to run uv run alembic upgrade head>
```

Do not offer to run upgrade yourself unless the user explicitly overrides project policy.
