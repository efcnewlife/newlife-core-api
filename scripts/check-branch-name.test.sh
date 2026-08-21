#!/usr/bin/env bash
# Black-box tests for scripts/check-branch-name.sh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CHECKER="${ROOT_DIR}/scripts/check-branch-name.sh"

pass_count=0
fail_count=0

assert_exit() {
  local expected_exit="$1"
  local branch="$2"
  local label="$3"
  local expect_substring="${4:-}"
  set +e
  output="$("${CHECKER}" "${branch}" 2>&1)"
  actual_exit=$?
  set -e
  if [[ "${actual_exit}" -ne "${expected_exit}" ]]; then
    fail_count=$((fail_count + 1))
    echo "FAIL: ${label}"
    echo "  branch: ${branch}"
    echo "  expected exit ${expected_exit}, got ${actual_exit}"
    echo "  output: ${output}"
    return
  fi
  if [[ -n "${expect_substring}" && "${output}" != *"${expect_substring}"* ]]; then
    fail_count=$((fail_count + 1))
    echo "FAIL: ${label} (missing guidance text)"
    echo "  expected substring: ${expect_substring}"
    echo "  output: ${output}"
    return
  fi
  pass_count=$((pass_count + 1))
}

assert_exit 0 "main" "allows main"
assert_exit 0 "develop" "allows develop"
assert_exit 0 "feat/69-enforce-branch-names" "allows feat with issue"
assert_exit 0 "fix/45-typo" "allows fix with issue"
assert_exit 0 "hotfix/9-prod-crash" "allows hotfix"
assert_exit 0 "refactor/1-cleanup" "allows refactor"
assert_exit 0 "perf/2-speed-up" "allows perf"
assert_exit 0 "test/3-add-coverage" "allows test"
assert_exit 0 "docs/4-readme" "allows docs"
assert_exit 0 "chore/7-deps" "allows chore"
assert_exit 0 "build/8-tooling" "allows build"
assert_exit 0 "ci/10-branch-check" "allows ci"
assert_exit 0 "release/1.4.0" "allows release semver"
assert_exit 0 "spike/explore-calendar" "allows spike without issue"

assert_exit 1 "feat/add-booking-grid" "rejects feat without issue" "Invalid branch name"
assert_exit 1 "Feat/1-foo" "rejects uppercase type" "Expected one of"
assert_exit 1 "feat/1-Foo" "rejects uppercase slug" "feat/69-enforce-branch-names"
assert_exit 1 "feat/1-" "rejects empty slug" "Invalid branch name"
assert_exit 1 "feat/1-bad--" "rejects consecutive hyphens" "Invalid branch name"
assert_exit 1 "feat/1--bad" "rejects leading hyphen in slug segment" "Invalid branch name"
assert_exit 1 "release/1.4.0-rc.1" "rejects release pre-release" "release/<major>.<minor>.<patch>"
assert_exit 1 "spike/" "rejects empty spike slug" "Invalid branch name"
assert_exit 1 "random-branch" "rejects unstructured name" "Invalid branch name"
assert_exit 1 "feature/1-foo" "rejects unknown type" "Invalid branch name"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "${fail_count} failed, ${pass_count} passed"
  exit 1
fi

echo "All ${pass_count} checks passed"
