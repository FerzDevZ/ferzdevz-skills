#!/usr/bin/env bash
# Install this pack into a Hermes profile's skills directory.
#   bin/install.sh                 -> ~/.hermes/skills
#   bin/install.sh --dest /path    -> custom target
#   bin/install.sh --dry-run       -> show what would change
#   bin/install.sh --backup        -> tar the target first (~/.hermes/backups/)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="${HOME}/.hermes/skills"
DRY=0
BACKUP=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dest) DEST="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    --backup) BACKUP=1; shift ;;
    -h|--help) sed -n '2,7p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# Never install the pack into itself, and never create skills/ inside skills/.
case "$DEST" in
  "$ROOT"|"$ROOT"/*) echo "destination is inside the pack: $DEST" >&2; exit 2 ;;
esac
if [[ -e "$DEST/skills" ]]; then
  echo "destination already contains a nested skills directory; run bin/doctor.py first" >&2
  exit 2
fi

[[ -f "$ROOT/CATALOG.md" ]] || python3 "$ROOT/bin/catalog.py" >/dev/null
python3 "$ROOT/bin/audit.py" --root "$ROOT" >/dev/null || {
  echo "audit failed; fix the pack before installing" >&2
  exit 1
}

if [[ $BACKUP -eq 1 && -d "$DEST" ]]; then
  STAMP="$(date +%Y%m%d-%H%M%S)"
  OUT="$HOME/.hermes/backups"
  mkdir -p "$OUT"
  tar -czf "$OUT/skills-$STAMP.tar.gz" -C "$(dirname "$DEST")" "$(basename "$DEST")"
  echo "backup: $OUT/skills-$STAMP.tar.gz"
fi

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

echo "$([[ $DRY -eq 1 ]] && echo 'would install' || echo 'installed') $count skill(s) into $DEST"
if [[ $DRY -eq 0 ]]; then
  python3 "$ROOT/bin/doctor.py" --profile "$DEST" --repo "$ROOT" || true
fi
