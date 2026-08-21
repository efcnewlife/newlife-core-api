#!/usr/bin/env bash
# Black-box tests for scripts/format-staged.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORMATTER="${ROOT_DIR}/scripts/format-staged.sh"
FIXTURE_DIR="${ROOT_DIR}/scripts/.format-staged-fixtures"
pass_count=0
fail_count=0

cleanup() {
  if [[ -d "${FIXTURE_DIR}" ]]; then
    git -C "${ROOT_DIR}" reset HEAD -- "${FIXTURE_DIR}" >/dev/null 2>&1 || true
    rm -rf "${FIXTURE_DIR}"
  fi
}
trap cleanup EXIT

mkdir -p "${FIXTURE_DIR}"

assert_true() {
  local label="$1"
  shift
  if "$@"; then
    pass_count=$((pass_count + 1))
  else
    fail_count=$((fail_count + 1))
    echo "FAIL: ${label}"
  fi
}

is_staged() {
  local rel="$1"
  git -C "${ROOT_DIR}" diff --cached --name-only -- "${rel}" | grep -qx "${rel}"
}

# --- formats and re-stages an ugly Python file ---
rel_ugly="scripts/.format-staged-fixtures/ugly_format.py"
ugly_file="${ROOT_DIR}/${rel_ugly}"
cat >"${ugly_file}" <<'PY'
def hello(  ):
    return   "world"
PY
git -C "${ROOT_DIR}" add -- "${rel_ugly}"

set +e
out="$("${FORMATTER}" 2>&1)"
status=$?
set -e

assert_true "format-staged exits 0 for formatable Python" test "${status}" -eq 0
assert_true "formatted file keeps double-quoted string" grep -q 'return "world"' "${ugly_file}"
assert_true "formatted file removes extra spaces in def" grep -q 'def hello():' "${ugly_file}"
assert_true "formatted file is still staged" is_staged "${rel_ugly}"
assert_true "working tree matches index for fixture" git -C "${ROOT_DIR}" diff --quiet -- "${rel_ugly}"

git -C "${ROOT_DIR}" reset HEAD -- "${rel_ugly}" >/dev/null
rm -f "${ugly_file}"

# --- fixes import order (I) and re-stages ---
rel_imports="scripts/.format-staged-fixtures/ugly_imports.py"
imports_file="${ROOT_DIR}/${rel_imports}"
cat >"${imports_file}" <<'PY'
import os
import sys

from portal.libs.tracing.distributed_trace import distributed_trace
import json
PY
git -C "${ROOT_DIR}" add -- "${rel_imports}"

set +e
out="$("${FORMATTER}" 2>&1)"
status=$?
set -e

assert_true "format-staged exits 0 when fixing imports" test "${status}" -eq 0
assert_true "import json is among stdlib imports" grep -q '^import json$' "${imports_file}"
assert_true "portal import remains" grep -q 'from portal.libs.tracing.distributed_trace import distributed_trace' "${imports_file}"
assert_true "imports file still staged" is_staged "${rel_imports}"

git -C "${ROOT_DIR}" reset HEAD -- "${rel_imports}" >/dev/null
rm -f "${imports_file}"

# --- no staged Python files: exit 0 ---
rel_txt="scripts/.format-staged-fixtures/note.txt"
non_py="${ROOT_DIR}/${rel_txt}"
echo "hello" >"${non_py}"
git -C "${ROOT_DIR}" add -- "${rel_txt}"
set +e
out="$("${FORMATTER}" 2>&1)"
status=$?
set -e
assert_true "format-staged exits 0 when no staged Python" test "${status}" -eq 0
git -C "${ROOT_DIR}" reset HEAD -- "${rel_txt}" >/dev/null
rm -f "${non_py}"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "${fail_count} failed, ${pass_count} passed"
  echo "${out:-}"
  exit 1
fi

echo "All ${pass_count} checks passed"
