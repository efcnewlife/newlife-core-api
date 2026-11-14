#!/usr/bin/env bash
# Point the staging Web App at an image digest and set its VERSION, then smoke-test /healthz (ADR 0039).
# Run by the CI staging deployment after az login; the operator uses it for manual staging redeploys and rollbacks.
# Changes only linuxFxVersion and VERSION; the newlife-infra app-service template owns every other setting.
# A failed smoke test is reported, never rolled back automatically. The smoke proves the site answers after the
# change, not which container answered: check the log stream or Sentry release for that.
#
# Usage: deploy-staging.sh <registry>/newlife-core-api@sha256:<digest> <7-character commit>
#   STAGING_RESOURCE_GROUP=rg-newlife-staging  STAGING_WEBAPP=app-newlife-api-stg
#   STAGING_URL=https://api.dev.efcnewlife.com  SMOKE_DELAY=60  SMOKE_TRIES=20  SMOKE_INTERVAL=15 (seconds)
set -euo pipefail

image="${1:-}"
release="${2:-}"
resource_group="${STAGING_RESOURCE_GROUP:-rg-newlife-staging}"
webapp="${STAGING_WEBAPP:-app-newlife-api-stg}"
url="${STAGING_URL:-https://api.dev.efcnewlife.com}"

if [[ -z "${image}" || -z "${release}" ]]; then
  echo "Usage: $0 <registry>/newlife-core-api@sha256:<digest> <7-character commit>" >&2
  exit 1
fi
if [[ ! "${image}" =~ ^[a-z0-9.-]+/newlife-core-api@sha256:[0-9a-f]{64}$ ]]; then
  echo "${image} is not a newlife-core-api digest reference" >&2
  exit 1
fi
if [[ ! "${release}" =~ ^[0-9a-f]{7}$ ]]; then
  echo "${release} is not a 7-character commit (staging VERSION, ADR 0038)" >&2
  exit 1
fi

app=(--resource-group "${resource_group}" --name "${webapp}")
wanted="DOCKER|${image}"
previous="$(az webapp config show "${app[@]}" --query linuxFxVersion -o tsv)"
echo "previous_image=${previous#DOCKER|}"

az webapp config appsettings set "${app[@]}" --settings "VERSION=${release}" -o none
az webapp config set "${app[@]}" --linux-fx-version "${wanted}" -o none

running="$(az webapp config show "${app[@]}" --query linuxFxVersion -o tsv)"
if [[ "${running}" != "${wanted}" ]]; then
  echo "${webapp} still runs ${running}, expected ${wanted}" >&2
  exit 1
fi

sleep "${SMOKE_DELAY:-60}"
tries="${SMOKE_TRIES:-20}"
for ((i = 1; i <= tries; i++)); do
  if curl --fail --silent --show-error --max-time 10 --output /dev/null "${url}/healthz"; then
    echo "smoke=passed"
    exit 0
  fi
  ((i < tries)) && sleep "${SMOKE_INTERVAL:-15}"
done

echo "smoke=failed"
echo "${url}/healthz did not answer 200 after ${tries} tries. No automatic rollback; previous image: ${previous#DOCKER|}" >&2
exit 1
