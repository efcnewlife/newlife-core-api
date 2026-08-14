# This application is managed with uv

newlife-core-api is an application, not a published package. uv is the toolchain: `uv.lock` is a freshly resolved, committed pin source, project metadata leaves runtime dependency names unpinned except gunicorn on the 25 series, redis-py on the 7 series, and cryptography on the 47 series, and `[tool.uv] required-version` plus the production image pin keep the uv binary on the same 0.12 series.

The `dev` group holds Alembic, Click, and the pytest stack; the production image runs `uv sync --frozen --no-dev --no-install-project` into a project `.venv` on `PATH`. Local Python is 3.14 via `.python-version`; the image uses `python:3.14-alpine` and does not install a second interpreter.

## Consequences

- Developers and agents install and run with `uv sync` / `uv run`.
- A stale lockfile fails the image build (`--frozen`).
- Seed and migration stay local-developer workflows; they are not in the runtime image.
