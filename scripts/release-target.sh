#!/usr/bin/env bash
# Decide what CI publishes for a Git ref (ADR 0039). Prints key=value lines for $GITHUB_OUTPUT.
#   main               -> publish image tag main-<12-char SHA>
#   x.y.z tag          -> publish image tag x.y.z, only when the commit is on an origin/release/* branch
#   any other branch   -> publish=false (CI and image build only)
#   any other tag      -> refused
# release is the staging VERSION / Sentry release: the 7-character commit (ADR 0038).
# Run inside a checkout that has the origin/release/* refs (fetch-depth 0).
#
# Usage: release-target.sh <branch|tag> <ref-name> <full-commit-sha>
set -euo pipefail

ref_type="${1:-}"
ref_name="${2:-}"
sha="${3:-}"

if [[ ! "${ref_type}" =~ ^(branch|tag)$ || -z "${ref_name}" || -z "${sha}" ]]; then
  echo "Usage: $0 <branch|tag> <ref-name> <full-commit-sha>" >&2
  exit 1
fi

if [[ ! "${sha}" =~ ^[0-9a-f]{40}$ ]]; then
  echo "${sha} is not a full 40-character commit SHA" >&2
  exit 1
fi

if [[ "${ref_type}" == "branch" ]]; then
  if [[ "${ref_name}" != "main" ]]; then
    echo "publish=false"
    exit 0
  fi
  image_tag="main-${sha:0:12}"
else
  if [[ ! "${ref_name}" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "${ref_name} is not an eligible release tag (x.y.z, no v prefix, no pre-release)" >&2
    exit 1
  fi
  if [[ -z "$(git branch --remotes --contains "${sha}" --list 'origin/release/*')" ]]; then
    echo "Tag ${ref_name} (${sha}) is not on any origin/release/* branch" >&2
    exit 1
  fi
  image_tag="${ref_name}"
fi

cat <<EOF
publish=true
image_tag=${image_tag}
release=${sha:0:7}
revision=${sha}
EOF
