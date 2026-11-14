#!/usr/bin/env bash
# Black-box tests for scripts/deploy-staging.sh with fake az and curl on PATH. Never contacts Azure.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY="${ROOT_DIR}/scripts/deploy-staging.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

NEW="efcnewlifecr.azurecr.io/newlife-core-api@sha256:$(printf 'b%.0s' {1..64})"
OLD="efcnewlifecr.azurecr.io/newlife-core-api@sha256:$(printf 'a%.0s' {1..64})"

pass_count=0
fail_count=0

# FAKE_RUNNING: linuxFxVersion before the change; FAKE_AFTER: what Azure reports after it (default: the requested one).
# FAKE_CURL_FAILS: number of failing health checks before one succeeds (999 = never).
mkdir -p "${WORK}/bin"
cat >"${WORK}/bin/az" <<'EOF'
#!/usr/bin/env bash
echo "az $*" >>"$FAKE_LOG"
state="$(dirname "$FAKE_LOG")/linux-fx"
case "$*" in
  "webapp config show"*) cat "$state" ;;
  "webapp config set"*)
    for arg in "$@"; do [[ "$arg" == DOCKER\|* ]] && echo "${FAKE_AFTER:-$arg}" >"$state"; done ;;
esac
exit 0
EOF
cat >"${WORK}/bin/curl" <<'EOF'
#!/usr/bin/env bash
echo "curl $*" >>"$FAKE_LOG"
count_file="$(dirname "$FAKE_LOG")/curl-count"
count=$(( $(cat "$count_file" 2>/dev/null || echo 0) + 1 ))
echo "$count" >"$count_file"
(( count > ${FAKE_CURL_FAILS:-0} ))
EOF
chmod +x "${WORK}/bin/az" "${WORK}/bin/curl"

run_deploy() {
  export FAKE_LOG="${WORK}/calls.log"
  : >"${FAKE_LOG}"
  rm -f "${WORK}/curl-count"
  echo "DOCKER|${OLD}" >"${WORK}/linux-fx"
  set +e
  output="$(PATH="${WORK}/bin:${PATH}" SMOKE_DELAY=0 SMOKE_INTERVAL=0 SMOKE_TRIES=3 "${DEPLOY}" "$@" 2>&1)"
  actual_exit=$?
  set -e
  calls="$(cat "${FAKE_LOG}")"
}

check() {
  local label="$1"
  shift
  if "$@"; then
    pass_count=$((pass_count + 1))
  else
    fail_count=$((fail_count + 1))
    echo "FAIL: ${label}"
    echo "  exit ${actual_exit}, output: ${output}"
    echo "  calls: ${calls}"
  fi
}
has() { [[ "$1" == *"$2"* ]]; }
lacks() { [[ "$1" != *"$2"* ]]; }

run_deploy "${NEW}" 1a2b3c4
check "deploy exits 0" test "${actual_exit}" -eq 0
check "deploy targets the staging app" has "${calls}" "--resource-group rg-newlife-staging --name app-newlife-api-stg"
check "deploy sets VERSION" has "${calls}" "--settings VERSION=1a2b3c4"
check "deploy sets the digest" has "${calls}" "--linux-fx-version DOCKER|${NEW}"
check "deploy records the previous image" has "${output}" "previous_image=${OLD}"
check "deploy reports smoke passed" has "${output}" "smoke=passed"
check "deploy checks /healthz" has "${calls}" "https://api-dev.efcnewlife.com/healthz"

run_deploy "${NEW}" 1a2b3c4
check "VERSION is set before the image" test \
  "$(grep -n 'appsettings set' <<<"${calls}" | cut -d: -f1)" -lt "$(grep -n 'config set' <<<"${calls}" | grep -v appsettings | cut -d: -f1)"

FAKE_CURL_FAILS=2 run_deploy "${NEW}" 1a2b3c4
check "smoke retries until healthy" test "${actual_exit}" -eq 0

FAKE_CURL_FAILS=999 run_deploy "${NEW}" 1a2b3c4
check "smoke failure fails" test "${actual_exit}" -ne 0
check "smoke failure reports" has "${output}" "smoke=failed"
check "smoke failure names the rollback target" has "${output}" "No automatic rollback; previous image: ${OLD}"
check "smoke failure does not roll back" test "$(grep -c 'config set --' <<<"${calls}" | tr -d ' ')" -eq 1

FAKE_AFTER="DOCKER|${OLD}" run_deploy "${NEW}" 1a2b3c4
check "unapplied image fails" test "${actual_exit}" -ne 0
check "unapplied image explains" has "${output}" "still runs DOCKER|${OLD}"

run_deploy "efcnewlifecr.azurecr.io/newlife-core-api:0.3.0" 1a2b3c4
check "tag reference is refused" test "${actual_exit}" -ne 0
check "tag reference does not touch the app" lacks "${calls}" "config set"

run_deploy "${NEW}" 0.3.0
check "non-commit release is refused" test "${actual_exit}" -ne 0

run_deploy "${NEW}"
check "missing release prints usage" has "${output}" "Usage:"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "${fail_count} failed, ${pass_count} passed"
  exit 1
fi

echo "All ${pass_count} checks passed"
