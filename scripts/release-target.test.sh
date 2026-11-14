#!/usr/bin/env bash
# Black-box tests for scripts/release-target.sh against a throwaway Git repository.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${ROOT_DIR}/scripts/release-target.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

pass_count=0
fail_count=0

# origin has main and release/0.3.0; the clone sees them as origin/*.
git init -q -b main "${WORK}/origin"
git -C "${WORK}/origin" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m base
git -C "${WORK}/origin" checkout -q -b release/0.3.0
git -C "${WORK}/origin" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m release-fix
git -C "${WORK}/origin" checkout -q main
git -C "${WORK}/origin" -c user.name=t -c user.email=t@example.com commit -q --allow-empty -m main-only
git clone -q "${WORK}/origin" "${WORK}/clone"
REPO="${WORK}/clone"
MAIN_SHA="$(git -C "${REPO}" rev-parse origin/main)"
RELEASE_SHA="$(git -C "${REPO}" rev-parse origin/release/0.3.0)"

run_target() {
  set +e
  output="$(cd "${REPO}" && "${TARGET}" "$@" 2>&1)"
  actual_exit=$?
  set -e
}

assert_target() {
  local label="$1" expected_exit="$2" expected="$3"
  shift 3
  run_target "$@"
  if [[ "${actual_exit}" -ne "${expected_exit}" || "${output}" != *"${expected}"* ]]; then
    fail_count=$((fail_count + 1))
    echo "FAIL: ${label}"
    echo "  expected exit ${expected_exit} with: ${expected}"
    echo "  got exit ${actual_exit}: ${output}"
    return
  fi
  pass_count=$((pass_count + 1))
}

main_out="publish=true
image_tag=main-${MAIN_SHA:0:12}
release=${MAIN_SHA:0:7}
revision=${MAIN_SHA}"
assert_target "main publishes main-<12>" 0 "${main_out}" branch main "${MAIN_SHA}"

tag_out="publish=true
image_tag=0.3.0
release=${RELEASE_SHA:0:7}
revision=${RELEASE_SHA}"
assert_target "release-branch tag publishes x.y.z" 0 "${tag_out}" tag 0.3.0 "${RELEASE_SHA}"

assert_target "release branch builds without publishing" 0 "publish=false" branch release/0.3.0 "${RELEASE_SHA}"
assert_target "topic branch builds without publishing" 0 "publish=false" branch feat/efc-311-x "${MAIN_SHA}"
assert_target "tag only on main is refused" 1 "not on any origin/release/* branch" tag 0.4.0 "${MAIN_SHA}"
assert_target "v-prefixed tag is refused" 1 "not an eligible release tag" tag v0.3.0 "${RELEASE_SHA}"
assert_target "two-part tag is refused" 1 "not an eligible release tag" tag 0.3 "${RELEASE_SHA}"
assert_target "pre-release tag is refused" 1 "not an eligible release tag" tag 0.3.0-rc.1 "${RELEASE_SHA}"
assert_target "leading zero tag is refused" 1 "not an eligible release tag" tag 0.03.0 "${RELEASE_SHA}"
assert_target "short SHA is refused" 1 "full 40-character commit SHA" branch main "${MAIN_SHA:0:12}"
assert_target "unknown ref type is refused" 1 "Usage:" pull 1 "${MAIN_SHA}"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "${fail_count} failed, ${pass_count} passed"
  exit 1
fi

echo "All ${pass_count} checks passed"
