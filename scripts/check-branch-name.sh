#!/usr/bin/env bash
# Validate a git branch name against the org naming convention.
# Usage: check-branch-name.sh <branch-name>
set -euo pipefail

branch="${1:-}"

if [[ -z "${branch}" ]]; then
  echo "Usage: $0 <branch-name>" >&2
  exit 1
fi

slug='[a-z0-9]+(-[a-z0-9]+)*'
topic_types='feat|fix|hotfix|refactor|perf|test|docs|chore|build|ci'

if [[ "${branch}" =~ ^(main|develop)$ ]]; then
  exit 0
fi

if [[ "${branch}" =~ ^release/[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  exit 0
fi

if [[ "${branch}" =~ ^spike/${slug}$ ]]; then
  exit 0
fi

# Issue number is a Linear id: optional lowercase team key + digits
# (e.g. efc-39) or a bare number (legacy).
if [[ "${branch}" =~ ^(${topic_types})/([a-z]+-)?[0-9]+-${slug}$ ]]; then
  exit 0
fi

cat >&2 <<EOF
Invalid branch name: ${branch}

Expected one of:
  main
  develop
  release/<major>.<minor>.<patch>          e.g. release/1.4.0
  spike/<short-description>                e.g. spike/explore-calendar
  <type>/<issue-number>-<short-description> e.g. feat/efc-39-booking-grid

Types: feat fix hotfix refactor perf test docs chore build ci
Issue number: Linear id (efc-39) or bare digits (39)
Short description: lowercase a-z, 0-9, single hyphens only
EOF
exit 1
