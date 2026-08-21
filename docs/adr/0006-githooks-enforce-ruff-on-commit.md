# .githooks enforce Ruff on commit

Ruff remains the Python formatter (ADR 0003). Commit-time enforcement uses this repo's `.githooks` directory via `core.hooksPath` (same install story as branch-name `pre-push`), not the Python `pre-commit` framework and not Husky. `.githooks/pre-commit` calls `scripts/format-staged.sh`, which runs `uv run ruff format` and `uv run ruff check --fix` (I-only) on staged `*.py` files and re-stages them.

## Considered Options

- **Python `pre-commit` package** — common, but a second hook installer beside `core.hooksPath=.githooks` for branch checks.
- **Husky / lint-staged** — Node-centric; wrong stack for this repo and conflicts with the org `.githooks` convention.
- **Document-only Ruff** — already failed to keep style consistent across editors and agents.

## Consequences

- Clone once: `./scripts/install-git-hooks.sh`.
- Emergency bypass: `git commit --no-verify` (local only).
- Do not broaden Ruff lint select beyond `I` in the hook.
