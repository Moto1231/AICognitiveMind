#!/usr/bin/env bash
set -euo pipefail

BRANCH="${1:-codex/autonomous-acceptance-loop}"
INTERVAL="${DEV_SYNC_INTERVAL:-3}"

current_branch="$(git branch --show-current)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  echo "Refusing to sync: current branch is '$current_branch', expected '$BRANCH'."
  exit 2
fi

echo "Watching origin/$BRANCH every ${INTERVAL}s."
echo "Sync pauses automatically if the working tree becomes dirty."

while true; do
  if ! git fetch origin "$BRANCH" --quiet; then
    echo "Fetch failed; retrying."
    sleep "$INTERVAL"
    continue
  fi

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "Working tree is dirty; automatic sync paused."
    sleep "$INTERVAL"
    continue
  fi

  local_sha="$(git rev-parse HEAD)"
  remote_sha="$(git rev-parse "origin/$BRANCH")"

  if [[ "$local_sha" != "$remote_sha" ]]; then
    if ! git merge-base --is-ancestor "$local_sha" "$remote_sha"; then
      echo "Remote branch is not a fast-forward from local HEAD; stopping for human review."
      exit 3
    fi

    echo "Fast-forwarding ${local_sha:0:12} -> ${remote_sha:0:12}"
    git merge --ff-only "origin/$BRANCH"
  fi

  sleep "$INTERVAL"
done
