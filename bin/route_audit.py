#!/usr/bin/env python3
"""Audit how a skill pack will be *selected*, not just how it is written.

An agent sees only `name` + `description` at discovery time. With more than ~50
skills the failure mode changes: it is no longer missing content, it is two skills
claiming the same trigger, or a description too generic to ever be chosen.

    bin/route_audit.py                 # report
    bin/route_audit.py --json
    bin/route_audit.py --fail-on-dupes # exit 1 when two descriptions collide

Heuristics, all printed with the evidence behind them:
  * collision   - description similarity >= 0.80 between two skills
  * generic     - description has < 3 content words after removing stopwords
  * weak        - description never names a concrete artifact (file, API, tool, metric)
  * overlap     - the same distinctive token appears in > 6 descriptions
"""
from __future__ import annotations

import argparse
import difflib
import json
import pathlib
import re
import sys

STOP = {
    "use", "when", "a", "an", "the", "is", "are", "was", "be", "to", "of", "for", "on",
    "in", "at", "it", "its", "and", "or", "that", "this", "with", "as", "by", "from",
    "your", "you", "needs", "need", "must", "should", "after", "before", "into", "not",
}
ARTIFACT = re.compile(
    r"\b(css|html|sql|json|yaml|docker|kubernetes|android|ios|flutter|react|next|pawn|"
    r"mysql|postgres|redis|streamer|textdraw|wcag|rag|llm|lcp|inp|cls|r8|hermes|"
    r"systemd|nginx|ci|api|sdk|bundle|token|schema|index|queue|cache)\b", re.I)


def read(p: pathlib.Path) -> dict:
    text = p.read_text(encoding="utf-8", errors="replace")
    fm = text.split("---", 2)[1] if text.startswith("---") else ""
    name = re.search(r"^name:\s*(\S+)", fm, re.M)
    desc = re.search(r"^description:\s*(.+)$", fm, re.M)
    return {
        "name": (name.group(1).strip('"') if name else p.parent.name),
        "description": (desc.group(1).strip().strip('"') if desc else ""),
        "category": p.parent.parent.name,
        "path": str(p),
    }


def content_words(desc: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+#.-]*", desc.lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def main() -> int:
    ap = argparse.ArgumentParser()
    here = pathlib.Path(__file__).resolve().parent.parent
    ap.add_argument("--root", default=str(here))
    ap.add_argument("--dupe-threshold", type=float, default=0.80)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-dupes", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    skills = [read(p) for p in sorted(root.glob("*/*/SKILL.md"))]
    if not skills:
        print(f"no skills under {root}")
        return 1

    collisions = []
    for i in range(len(skills)):
        for j in range(i + 1, len(skills)):
            a, b = skills[i], skills[j]
            ratio = difflib.SequenceMatcher(None, a["description"].lower(),
                                            b["description"].lower()).ratio()
            if ratio >= args.dupe_threshold:
                collisions.append((round(ratio, 3), a["name"], b["name"]))
    collisions.sort(reverse=True)

    generic = [s for s in skills if len(content_words(s["description"])) < 3]
    # NOTE: an "artifact named" heuristic was tried and removed. It flagged 129/165
    # skills that do name their subject ("ML metric", "container image"), because any
    # keyword list is narrower than the vocabulary a good description uses. A metric
    # that noisy teaches the reader to ignore the report.

    token_owner: dict[str, list[str]] = {}
    for s in skills:
        for w in set(content_words(s["description"])):
            token_owner.setdefault(w, []).append(s["name"])
    crowded = sorted(((len(v), k, v) for k, v in token_owner.items() if len(v) > 6), reverse=True)

    if args.json:
        print(json.dumps({"skills": len(skills), "collisions": collisions,
                          "generic": [s["name"] for s in generic],
                          "crowded_tokens": [{"token": k, "skills": v} for _, k, v in crowded]},
                         indent=1))
    else:
        print(f"route audit: {len(skills)} skills, "
              f"{len({s['category'] for s in skills})} categories")
        print(f"\ncollisions (>= {args.dupe_threshold:.2f} description similarity): {len(collisions)}")
        for ratio, a, b in collisions[:12]:
            print(f"  {ratio:.2f}  {a}  <->  {b}")
        print(f"\ngeneric descriptions (< 3 content words): {len(generic)}")
        for s in generic[:12]:
            print(f"  {s['name']}: {s['description']!r}")
        print("\ntokens shared by more than 6 descriptions:")
        for n, token, owners in crowded[:10]:
            print(f"  {token!r} x{n}: " + ", ".join(owners[:5]) + (" …" if n > 5 else ""))

    if args.fail_on_dupes and collisions:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
