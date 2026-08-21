#!/usr/bin/env bash
# Point this clone at the repo's .githooks directory.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

git config core.hooksPath .githooks
chmod +x \
  .githooks/pre-push \
  .githooks/pre-commit \
  scripts/check-branch-name.sh \
  scripts/check-branch-name.test.sh \
  scripts/format-staged.sh \
  scripts/format-staged.test.sh \
  scripts/install-git-hooks.sh

echo "Installed git hooks (core.hooksPath=.githooks)"
echo "Emergency bypass: git commit --no-verify / git push --no-verify"
