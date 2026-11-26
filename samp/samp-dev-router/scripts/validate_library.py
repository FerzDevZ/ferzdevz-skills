#!/usr/bin/env python3
"""Check the samp/ skill library: structure, required sections, name/dir parity."""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]  # .../skills/samp
REQUIRED = [
    "## When to Use",
    "## 2026 Compatibility & Architecture Matrix",
    "## Production Implementation",
    "## Deprecated Traps & Edge Cases (2026)",
    "## Verification",
]


def main() -> int:
    problems = []
    skills = sorted(ROOT.glob("*/SKILL.md"))
    for path in skills:
        d = path.parent.name
        text = path.read_text(encoding="utf-8", errors="replace")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            problems.append(f"{d}: missing frontmatter")
            continue
        meta = m.group(1)
        name = re.search(r"^name:\s*(\S+)", meta, re.M)
        desc = re.search(r"^description:\s*(.+)$", meta, re.M)
        if not name:
            problems.append(f"{d}: missing name")
        elif name.group(1) != d:
            problems.append(f"{d}: name is {name.group(1)}")
        if not desc or not desc.group(1).strip():
            problems.append(f"{d}: missing description")
        if 'version: "2026.1.0"' not in meta:
            problems.append(f"{d}: version not 2026.1.0")
        if "category: samp" not in meta:
            problems.append(f"{d}: category not samp")
        for section in REQUIRED:
            if section not in text:
                problems.append(f"{d}: missing section {section}")
        if re.search(r"\b(TODO|FIXME|TBD)\b", text):
            problems.append(f"{d}: unfinished marker")

    print(f"{len(skills)} skills, {len(problems)} problems")
    for p in problems:
        print("  - " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
