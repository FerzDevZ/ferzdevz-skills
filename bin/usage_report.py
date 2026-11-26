#!/usr/bin/env python3
"""Report which pack skills were actually loaded, from the Hermes session database.

A skill that is never loaded is either unknown to the agent (description problem) or not
needed (deletion candidate). This reads `messages.tool_name = 'skill_view'` rows, extracts
the skill name from the tool call arguments, and compares with the pack on disk.

    bin/usage_report.py
    bin/usage_report.py --days 30 --db ~/.hermes/state.db
    bin/usage_report.py --json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sqlite3
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent


def pack_skills(root: pathlib.Path) -> set[str]:
    return {p.parent.name for p in root.glob("*/*/SKILL.md")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--db", default=str(pathlib.Path.home() / ".hermes" / "state.db"))
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    known = pack_skills(root)
    db = pathlib.Path(args.db).expanduser()
    if not db.is_file():
        print(f"no session database at {db}")
        return 2

    since = time.time() - args.days * 86400
    counts: collections.Counter[str] = collections.Counter()
    unknown: collections.Counter[str] = collections.Counter()
    rows = 0
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        cur = con.execute(
            "SELECT tool_calls, content FROM messages "
            "WHERE tool_name = 'skill_view' AND timestamp >= ?", (since,))
        for tool_calls, content in cur:
            blob = (tool_calls or "") + " " + (content or "")
            names = re.findall(r'"name"\s*:\s*"([a-z0-9][a-z0-9-]+)"', blob)
            names += re.findall(r"skill_view\(([a-z0-9][a-z0-9-]+)\)", blob)
            for n in names:
                rows += 1
                (counts if n in known else unknown)[n] += 1
    finally:
        con.close()

    used = counts.most_common()
    never = sorted(known - set(counts))
    out = {"window_days": args.days, "lookups": rows, "used": used,
           "never_used": never, "outside_pack": unknown.most_common()}
    if args.json:
        print(json.dumps(out, indent=1))
        return 0

    print(f"skill lookups in the last {args.days} days: {rows}")
    if not rows:
        print("no skill_view calls recorded yet — run a few tasks, then re-run this.")
    for name, n in used[:15]:
        print(f"  {n:4}  {name}")
    if unknown:
        print("  outside this pack: " + ", ".join(f"{n} x{c}" for n, c in unknown.most_common(5)))
    print(f"\nnever loaded: {len(never)} of {len(known)} pack skills")
    if never:
        print("  " + ", ".join(never[:20]) + (" …" if len(never) > 20 else ""))
    print("\nRead this as a hint, not a verdict: a skill can be loaded without being counted "
          "(subagents, other clients) and an unloaded skill can still be the right one next week.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
