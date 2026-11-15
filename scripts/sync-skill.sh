#!/usr/bin/env bash
set -euo pipefail
SRC="${1:-$HOME/Desktop/superskills/skills/video-analiz}"
DST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/skills/video-analiz"
if [ ! -f "$SRC/SKILL.md" ]; then
  echo "error: $SRC/SKILL.md not found" >&2
  exit 1
fi
mkdir -p "$DST"
rsync -a --delete --exclude '*-workspace/' --exclude '.DS_Store' "$SRC/" "$DST/"
echo "synced $SRC -> $DST"
