#!/usr/bin/env bash
# Install this pack into a Hermes profile's skills directory.
#   bin/install.sh                 -> ~/.hermes/skills
#   bin/install.sh --dest /path    -> custom target
#   bin/install.sh --dry-run       -> show what would change
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/.hermes/skills"
DRY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$ROOT/CATALOG.md" ]] || python3 "$ROOT/bin/catalog.py" >/dev/null
python3 "$ROOT/bin/audit.py" --root "$ROOT" >/dev/null || {
  echo "audit failed; fix the pack before installing" >&2
  exit 1
}

count=0
for dir in "$ROOT"/*/*/SKILL.md; do
  cat="$(basename "$(dirname "$(dirname "$dir")")")"
  name="$(basename "$(dirname "$dir")")"
  src="$(dirname "$dir")"
  dst="$DEST/$cat/$name"
  if [[ $DRY -eq 1 ]]; then
    echo "would install $cat/$name -> $dst"
  else
    mkdir -p "$dst"
    cp -a "$src/." "$dst/"
  fi
  count=$((count + 1))
done

echo "installed $count skill(s) into $DEST"
