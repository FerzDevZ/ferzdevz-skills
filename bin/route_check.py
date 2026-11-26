#!/usr/bin/env python3
"""Check that realistic requests route to the intended skill.

This is a proxy, not the model's own choice: it ranks every description by IDF-weighted
token overlap with the prompt. A miss here means the description lacks the words a user
actually types, which is fixable text, not a model mystery.

    bin/route_check.py                 # summary + misses
    bin/route_check.py --verbose       # top-3 per case
    bin/route_check.py --json
"""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOP = {"the", "a", "an", "and", "or", "to", "of", "in", "on", "for", "with", "is", "are",
        "was", "be", "it", "its", "our", "we", "you", "your", "that", "this", "not",
        "use", "when", "after", "before", "but", "so", "no", "all", "at", "by", "from"}


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9][a-z0-9+#._-]*", text.lower())
    return [w for w in words if w not in STOP and len(w) > 2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--cases", default="")
    ap.add_argument("--min-recall", type=float, default=1.0,
                    help="fail when recall@1 is below this (0-1)")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    cases_path = pathlib.Path(args.cases) if args.cases else root / "evals" / "routing.json"
    cases = json.loads(cases_path.read_text())["cases"]

    docs: dict[str, list[str]] = {}
    for p in sorted(root.glob("*/*/SKILL.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        fm = text.split("---", 2)[1] if text.startswith("---") else ""
        name = p.parent.name.replace("-", " ")
        desc = ""
        m = re.search(r"^description:\s*(.+)$", fm, re.M)
        if m:
            desc = m.group(1).strip().strip('"')
        # body headings carry a lot of the vocabulary a user would use
        heads = " ".join(re.findall(r"^#{2,3} (.+)$", text, re.M))
        # field weights: a name or description token is worth far more than a body heading
        docs[p.parent.name] = (tokens(name) * 3) + (tokens(desc) * 2) + tokens(heads)

    df: dict[str, int] = {}
    for toks in docs.values():
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    idf = {t: math.log((n + 1) / (c + 0.5)) for t, c in df.items()}

    def rank(prompt: str) -> list[tuple[float, str]]:
        qt = set(tokens(prompt))
        scored = []
        for skill, toks in docs.items():
            tf: dict[str, int] = {}
            for t in toks:
                if t in qt:
                    tf[t] = tf.get(t, 0) + 1
            score = sum(idf.get(t, 0.0) * (1 + math.log(c)) for t, c in tf.items())
            scored.append((score, skill))
        scored.sort(reverse=True)
        return scored[:5]

    hits1 = hits3 = 0
    misses = []
    for c in cases:
        ranked = rank(c["prompt"])
        top = [s for _, s in ranked]
        ok1 = top[0] == c["expect"]
        ok3 = c["expect"] in top[:3]
        hits1 += ok1
        hits3 += ok3
        if not ok1:
            misses.append({"prompt": c["prompt"], "expect": c["expect"],
                           "got": top[0], "top3": top[:3]})
        if args.verbose:
            print(f"\n{c['prompt'][:70]}")
            print(f"  expect {c['expect']}  got {top[0]}  {'OK' if ok1 else 'MISS'}")
            for score, s in ranked[:3]:
                print(f"    {score:6.2f}  {s}")

    total = len(cases)
    if args.json:
        print(json.dumps({"cases": total, "recall@1": hits1 / total, "recall@3": hits3 / total,
                          "misses": misses}, indent=1))
    else:
        print(f"routing: {total} cases, recall@1 {hits1}/{total} ({hits1/total:.0%}), "
              f"recall@3 {hits3}/{total} ({hits3/total:.0%})")
        for m in misses:
            print(f"\nMISS  {m['prompt'][:64]}")
            print(f"  expected {m['expect']}, got {m['got']}")
            print(f"  top3: {', '.join(m['top3'])}")
    return 0 if hits1 / total >= args.min_recall else 1


if __name__ == "__main__":
    sys.exit(main())
