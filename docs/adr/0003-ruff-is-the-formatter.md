# Ruff is the Python formatter

newlife-core-api had no project-owned formatter; agent docs forbade Black, isort, and flake8, so style lived in personal IDEs. Ruff, invoked through uv, is the only Python formatter: `uv run ruff format` then `uv run ruff check --fix`. Import sorting is Ruff rule family I only (`lint.select` locked to `I`; `portal` is first-party). Full lint, including Ruff's default E/F rules, stays off. Line length is 160 to match EditorConfig; Ruff hard-wraps at that width and does not clone PyCharm wrap, align, or keep-line-breaks. Quotes are preserved. Alembic version scripts are excluded; `alembic/env.py` is included. PyCharm's built-in Python formatter is not a second contract — use Ruff (or a Ruff plugin that reads the same project settings).

## Considered Options

- **Black + isort** — two binaries; already forbidden in agent docs; Ruff replaces both under uv.
- **Ruff format only, no I** — import order would stay editor-specific.
- **Ruff as a full linter** — rejected this round; that would reverse the no-lint policy rather than adopt a formatter.
- **Line length 88** — Black default; contradicts EditorConfig `max_line_length = 160`.

## Consequences

- Developers and agents format with the two uv commands; do not run Black, isort, or flake8.
- A bare `ruff check` must not grow `lint.select` beyond `I`.
- `isort.split-on-trailing-comma` is false so it does not fight `skip-magic-trailing-comma`.
- EditorConfig `ij_python_*` wrap/align keys are historical, not the team contract.
