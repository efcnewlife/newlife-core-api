#!/usr/bin/env bash
# Format and lint-fix staged Python files, then re-stage them.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

mapfile -t staged_files < <(
  git diff --cached --name-only --diff-filter=ACMR -- '*.py' \
    | while IFS= read -r path; do
        [[ -f "${path}" ]] && printf '%s\n' "${path}"
      done
)

if [[ "${#staged_files[@]}" -eq 0 ]]; then
  exit 0
fi

uv run ruff format --force-exclude -- "${staged_files[@]}"
uv run ruff check --fix --force-exclude --select I -- "${staged_files[@]}"
git add -- "${staged_files[@]}"
