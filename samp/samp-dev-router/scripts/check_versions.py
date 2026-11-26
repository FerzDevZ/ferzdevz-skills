#!/usr/bin/env python3
"""Flag version strings that are not in the pinned baseline."""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).resolve().parent
ASSETS = HERE.parent / "assets"
ROOT = HERE.parents[1]
KNOWN = set()
for v in json.loads((ASSETS / "versions.json").read_text()).values():
    if isinstance(v, list):
        KNOWN.update(v)

PAT = re.compile(r"\bv?(\d+\.\d+(?:\.\d+){0,2})\b")

def main() -> int:
    unknown = {}
    for p in sorted(ROOT.glob("*/SKILL.md")):
        for v in set(PAT.findall(p.read_text(errors="replace"))):
            if v not in KNOWN:
                unknown.setdefault(v, set()).add(p.parent.name)
    print(f"{len(unknown)} version strings outside the baseline")
    for v, skills in sorted(unknown.items()):
        print(f"  {v}: " + ", ".join(sorted(skills)[:4]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
