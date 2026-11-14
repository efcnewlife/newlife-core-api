#!/usr/bin/env bash
# Push a locally built, smoke-tested Core API image to ACR under an immutable tag, then lock the tag and digest
# (docs/azure-container-registry.md). Run by the CI staging publication after az login; the operator may run it too.
#   - The local image's org.opencontainers.image.revision label must equal <revision>.
#   - A tag that already exists is never overwritten. If it carries the same revision (a rerun), its digest is reused.
#   - Listing repositories or tags, or locking, failing stops the publication.
# Prints key=value lines for $GITHUB_OUTPUT: digest, image (digest reference), reused.
#
# Usage: acr-publish.sh <local-image> <image-tag> <revision>
#   ACR_NAME=efcnewlifecr  registry name
set -euo pipefail

local_image="${1:-}"
tag="${2:-}"
revision="${3:-}"
registry="${ACR_NAME:-efcnewlifecr}"
repository="newlife-core-api"
login_server="${registry}.azurecr.io"
remote="${login_server}/${repository}"

if [[ -z "${local_image}" || -z "${tag}" || -z "${revision}" ]]; then
  echo "Usage: $0 <local-image> <image-tag> <revision>" >&2
  exit 1
fi

revision_label='{{ index .Config.Labels "org.opencontainers.image.revision" }}'
local_revision="$(docker image inspect --format "${revision_label}" "${local_image}")"
if [[ "${local_revision}" != "${revision}" ]]; then
  echo "${local_image} has revision label ${local_revision}, expected ${revision}" >&2
  exit 1
fi

az acr login --name "${registry}" >/dev/null

existing_tags=""
repositories="$(az acr repository list --name "${registry}" -o tsv)"
if grep -Fxq -- "${repository}" <<<"${repositories}"; then
  existing_tags="$(az acr repository show-tags --name "${registry}" --repository "${repository}" -o tsv)"
fi
if grep -Fxq -- "${tag}" <<<"${existing_tags}"; then
  remote_revision="$(docker buildx imagetools inspect "${remote}:${tag}" \
    --format '{{ index .Image.Config.Labels "org.opencontainers.image.revision" }}')"
  if [[ "${remote_revision}" != "${revision}" ]]; then
    echo "${remote}:${tag} already exists for revision ${remote_revision}; refusing to overwrite it with ${revision}" >&2
    exit 1
  fi
  reused=true
else
  docker tag "${local_image}" "${remote}:${tag}"
  docker push "${remote}:${tag}" >/dev/null
  reused=false
fi

digest="$(az acr repository show --name "${registry}" --image "${repository}:${tag}" --query digest -o tsv)"
az acr repository update --name "${registry}" --image "${repository}:${tag}" --write-enabled false >/dev/null
az acr repository update --name "${registry}" --image "${repository}@${digest}" --write-enabled false >/dev/null

cat <<EOF
digest=${digest}
image=${remote}@${digest}
reused=${reused}
EOF
