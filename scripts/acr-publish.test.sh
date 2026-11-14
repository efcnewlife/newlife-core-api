#!/usr/bin/env bash
# Black-box tests for scripts/acr-publish.sh with fake az and docker on PATH. Never contacts Azure.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLISH="${ROOT_DIR}/scripts/acr-publish.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

REV="1111111111111111111111111111111111111111"
OTHER="2222222222222222222222222222222222222222"
DIGEST="sha256:aaaa"

pass_count=0
fail_count=0

# Fakes log every call to $FAKE_LOG. FAKE_TAGS: tags already in ACR. FAKE_REMOTE_REV: revision label of the
# existing remote tag. FAKE_LOCAL_REV: revision label of the local image. FAKE_FAIL: a command word that fails.
mkdir -p "${WORK}/bin"
cat >"${WORK}/bin/az" <<'EOF'
#!/usr/bin/env bash
echo "az $*" >>"$FAKE_LOG"
[[ -n "${FAKE_FAIL:-}" && "$*" == *"${FAKE_FAIL}"* ]] && { echo "fake failure" >&2; exit 1; }
case "$*" in
  "acr repository list"*) printf '%s\n' ${FAKE_REPOS-newlife-core-api} ;;
  "acr repository show-tags"*) printf '%s\n' ${FAKE_TAGS:-} ;;
  "acr repository show "*) echo "sha256:aaaa" ;;
esac
EOF
cat >"${WORK}/bin/docker" <<'EOF'
#!/usr/bin/env bash
echo "docker $*" >>"$FAKE_LOG"
[[ -n "${FAKE_FAIL:-}" && "$*" == *"${FAKE_FAIL}"* ]] && { echo "fake failure" >&2; exit 1; }
case "$*" in
  "image inspect"*) echo "${FAKE_LOCAL_REV}" ;;
  "buildx imagetools inspect"*) echo "${FAKE_REMOTE_REV:-}" ;;
esac
EOF
chmod +x "${WORK}/bin/az" "${WORK}/bin/docker"

run_publish() {
  export FAKE_LOG="${WORK}/calls.log"
  : >"${FAKE_LOG}"
  set +e
  output="$(PATH="${WORK}/bin:${PATH}" "${PUBLISH}" "$@" 2>&1)"
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

# New tag: push, lock tag and digest, print the digest reference.
FAKE_TAGS="0.2.0 main-000000000000" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "new tag exits 0" test "${actual_exit}" -eq 0
check "new tag pushes" has "${calls}" "docker push efcnewlifecr.azurecr.io/newlife-core-api:0.3.0"
check "new tag locks the tag" has "${calls}" "--image newlife-core-api:0.3.0 --write-enabled false"
check "new tag locks the digest" has "${calls}" "--image newlife-core-api@${DIGEST} --write-enabled false"
check "new tag prints digest" has "${output}" "digest=${DIGEST}"
check "new tag prints image ref" has "${output}" "image=efcnewlifecr.azurecr.io/newlife-core-api@${DIGEST}"
check "new tag is not reused" has "${output}" "reused=false"

# Rerun for the same commit: reuse the existing digest without pushing.
FAKE_TAGS="0.3.0" FAKE_REMOTE_REV="${REV}" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "rerun exits 0" test "${actual_exit}" -eq 0
check "rerun does not push" lacks "${calls}" "docker push"
check "rerun reuses" has "${output}" "reused=true"
check "rerun prints digest" has "${output}" "digest=${DIGEST}"

# Existing tag from another commit: never overwrite.
FAKE_TAGS="0.3.0" FAKE_REMOTE_REV="${OTHER}" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "foreign tag fails" test "${actual_exit}" -ne 0
check "foreign tag is not pushed" lacks "${calls}" "docker push"
check "foreign tag explains" has "${output}" "already exists for revision ${OTHER}"

# Local image built from another commit: refuse before touching ACR.
FAKE_TAGS="" FAKE_LOCAL_REV="${OTHER}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "label mismatch fails" test "${actual_exit}" -ne 0
check "label mismatch does not log in" lacks "${calls}" "acr login"
check "label mismatch explains" has "${output}" "revision label ${OTHER}"

# Tag listing fails (no access, no repository): fail closed instead of assuming the tag is free.
FAKE_FAIL="show-tags" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "listing failure fails" test "${actual_exit}" -ne 0
check "listing failure does not push" lacks "${calls}" "docker push"

FAKE_FAIL="repository list" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "repository listing failure fails" test "${actual_exit}" -ne 0
check "repository listing failure does not push" lacks "${calls}" "docker push"

# First publication: the repository does not exist yet, so there are no tags to list.
FAKE_REPOS="other-app" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "first publication exits 0" test "${actual_exit}" -eq 0
check "first publication does not list tags" lacks "${calls}" "show-tags"
check "first publication pushes" has "${calls}" "docker push efcnewlifecr.azurecr.io/newlife-core-api:0.3.0"

# Lock refused: fail so the deployment does not continue with an unlocked release image.
FAKE_FAIL="--write-enabled false" FAKE_TAGS="" FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0 "${REV}"
check "lock failure fails" test "${actual_exit}" -ne 0
check "lock failure prints no digest" lacks "${output}" "digest="

# Arguments.
FAKE_LOCAL_REV="${REV}" run_publish newlife-core-api:ci 0.3.0
check "missing revision fails with usage" has "${output}" "Usage:"

if [[ "${fail_count}" -gt 0 ]]; then
  echo "${fail_count} failed, ${pass_count} passed"
  exit 1
fi

echo "All ${pass_count} checks passed"
