#!/usr/bin/env bash
# Offline Bicep validation for infra/azure: compile, lint, and format check every template and
# parameter file. Fails on any warning. Never signs in to Azure or calls what-if/deploy.
#
# Usage: scripts/validate-bicep.sh
#   BICEP=/path/to/bicep  compiler to use (default: bicep on PATH, else ~/.azure/bin/bicep from `az bicep install`)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -n "${BICEP:-}" ]; then
  BICEP="$(command -v "$BICEP" || true)"
else
  BICEP="$(command -v bicep || echo "$HOME/.azure/bin/bicep")"
fi
[ -n "$BICEP" ] && [ -x "$BICEP" ] || { echo "bicep not found; install it with: az bicep install" >&2; exit 1; }

# Parameter files read secrets from the environment at deploy time; offline compilation needs only a placeholder.
export NEWLIFE_PG_ADMIN_PASSWORD="${NEWLIFE_PG_ADMIN_PASSWORD:-offline-validation-placeholder}"
export NEWLIFE_API_IMAGE_DIGEST="${NEWLIFE_API_IMAGE_DIGEST:-sha256:offline-validation-placeholder}"
export NEWLIFE_API_RELEASE="${NEWLIFE_API_RELEASE:-offline}"

files="$(find "$ROOT/infra/azure" -name '*.bicep' -o -name '*.bicepparam' | sort)"
[ -n "$files" ] || { echo "no Bicep files under infra/azure" >&2; exit 1; }

status=0
while IFS= read -r file; do
  rel="${file#"$ROOT"/}"
  ok=1
  case "$file" in
    *.bicepparam) out="$("$BICEP" build-params "$file" --stdout 2>&1 >/dev/null)" || ok=0 ;;
    *) out="$("$BICEP" lint "$file" 2>&1)" || ok=0 ;;
  esac
  if [ -n "$out" ]; then
    printf '%s\n' "$out" >&2
    ok=0
  fi
  if ! "$BICEP" format "$file" --stdout | diff -q "$file" - >/dev/null; then
    echo "$rel: not formatted (run: $BICEP format $rel)" >&2
    ok=0
  fi
  if [ "$ok" = 1 ]; then echo "ok $rel"; else echo "FAIL $rel" >&2; status=1; fi
done <<<"$files"

exit "$status"
