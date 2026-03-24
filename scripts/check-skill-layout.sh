#!/usr/bin/env bash
set -euo pipefail

root="${1:-skills}"

status=0

for skill in "$root"/daggerheart-*; do
  [ -d "$skill" ] || continue
  if [ ! -f "$skill/SKILL.md" ]; then
    echo "Missing SKILL.md: $skill"
    status=1
  fi
  if [ ! -d "$skill/references" ]; then
    echo "Missing references/: $skill"
    status=1
  fi
  if [ ! -d "$skill/assets" ]; then
    echo "Missing assets/: $skill"
    status=1
  fi
done

exit "$status"
