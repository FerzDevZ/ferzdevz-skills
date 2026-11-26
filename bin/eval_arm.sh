#!/usr/bin/env bash
# Run one eval arm in an isolated HOME, so the real profile is never moved.
#
#   bin/eval_arm.sh with    --dir /tmp/ev/with    --prompt /tmp/ev/prompt.txt
#   bin/eval_arm.sh without --dir /tmp/ev/without --prompt /tmp/ev/prompt.txt
#
# Why a temp HOME: a nested `hermes chat` recreates ~/.hermes/skills when the directory is
# missing, so moving the real one aside leaves two trees and the restore fails. Here the arm
# gets its own HOME: config.yaml and .env are copied, skills is a symlink to the real pack
# ("with") or absent ("without").
set -euo pipefail

ARM="${1:-}"
shift || true
DIR=""
PROMPT=""
MAX_TURNS=20
BUDGET=420
REAL_HOME="${HOME}"
SKILLS="${REAL_HOME}/.hermes/skills"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dir) DIR="$2"; shift 2 ;;
    --prompt) PROMPT="$2"; shift 2 ;;
    --max-turns) MAX_TURNS="$2"; shift 2 ;;
    --budget) BUDGET="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ "$ARM" == "with" || "$ARM" == "without" ]] || { echo "usage: $0 with|without --dir D --prompt P" >&2; exit 2; }
[[ -d "$DIR" ]] || { echo "no work dir: $DIR" >&2; exit 2; }
[[ -f "$PROMPT" ]] || { echo "no prompt file: $PROMPT" >&2; exit 2; }
[[ -d "$SKILLS" ]] || { echo "real skills dir missing: $SKILLS" >&2; exit 2; }

TH="$(mktemp -d "${TMPDIR:-/tmp}/ferz-arm-$ARM-XXXXXX")"
cleanup() { rm -rf "$TH"; }
trap cleanup EXIT INT TERM

mkdir -p "$TH/.hermes"
for f in config.yaml .env; do
  [[ -f "$REAL_HOME/.hermes/$f" ]] && cp "$REAL_HOME/.hermes/$f" "$TH/.hermes/$f"
done
if [[ "$ARM" == "with" ]]; then
  ln -s "$SKILLS" "$TH/.hermes/skills"
fi

COUNT="$(find "$TH/.hermes" -maxdepth 3 -name SKILL.md 2>/dev/null | wc -l)"
echo "arm=$ARM dir=$DIR isolated_home=$TH skills_visible=$COUNT"

HOME="$TH" hermes chat -q "$(cat "$PROMPT")" --oneshot --in "$DIR" \
  --max-turns "$MAX_TURNS" --run-budget "$BUDGET" --yolo -Q

echo "arm=$ARM done; real profile untouched ($(find "$SKILLS" -maxdepth 3 -name SKILL.md | wc -l) skills)"
