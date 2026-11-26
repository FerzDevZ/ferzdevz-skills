#!/usr/bin/env python3
"""Check that an installed profile matches the pack, and catch the failure modes that
actually happened: duplicated skill names from two trees, a nested skills directory,
directories copied without SKILL.md, and categories that silently went missing.

    bin/doctor.py
    bin/doctor.py --profile ~/.hermes/skills --repo .
"""
from __future__ import annotations

import argparse
import collections
import pathlib
import sys


def skill_dirs(root: pathlib.Path) -> list[pathlib.Path]:
    return sorted(root.glob("*/*/SKILL.md"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=str(pathlib.Path.home() / ".hermes" / "skills"))
    ap.add_argument("--repo", default=str(pathlib.Path(__file__).resolve().parent.parent))
    args = ap.parse_args()

    profile = pathlib.Path(args.profile).expanduser().resolve()
    repo = pathlib.Path(args.repo).expanduser().resolve()
    problems: list[str] = []
    notes: list[str] = []

    if not profile.is_dir():
        print(f"FAIL profile does not exist: {profile}")
        return 1

    installed = skill_dirs(profile)
    pack = skill_dirs(repo)
    pack_names = {p.parent.name for p in pack}
    inst_names = {p.parent.name for p in installed}

    print(f"profile: {profile}")
    print(f"  skills: {len(installed)}  categories: {len({p.parent.parent.name for p in installed})}")
    print(f"repo:    {repo}")
    print(f"  skills: {len(pack)}  categories: {len({p.parent.parent.name for p in pack})}")

    # 1. nested skills tree (a skills dir copied inside skills)
    nested = [d for d in profile.iterdir() if d.is_dir() and d.name.startswith(("skills", "samp-legacy"))]
    for d in nested:
        if (d / "samp").is_dir() or (d / "web-dev").is_dir():
            problems.append(f"nested skill tree inside the profile: {d} "
                            f"({len(skill_dirs(d))} skills) — move it out, do not leave two copies")

    # 2. duplicate names across different categories
    counts = collections.Counter(p.parent.name for p in installed)
    dupes = {n: c for n, c in counts.items() if c > 1}
    if dupes:
        for name, count in sorted(dupes.items()):
            where = [str(p.parent.parent.name) for p in installed if p.parent.name == name]
            problems.append(f"duplicate skill name '{name}' x{count} in {', '.join(where)}")

    # 3. repo skills missing from the profile
    missing = sorted(pack_names - inst_names)
    if missing:
        problems.append(f"{len(missing)} pack skill(s) not installed: "
                        + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else ""))

    # 4. directories that look like skills but have no SKILL.md
    for cat in sorted({p.parent.parent for p in installed}):
        for d in sorted(cat.iterdir()):
            if d.is_dir() and not (d / "SKILL.md").is_file():
                notes.append(f"directory without SKILL.md: {d.relative_to(profile)}")

    # 5. frontmatter name vs folder
    for p in installed:
        head = p.read_text(encoding="utf-8", errors="replace")[:400]
        if "name:" in head:
            declared = head.split("name:", 1)[1].split("\n", 1)[0].strip().strip('"')
            if declared and declared != p.parent.name:
                problems.append(f"name mismatch: {p.relative_to(profile)} declares '{declared}'")

    print()
    for n in notes:
        print("note  " + n)
    if problems:
        for p in problems:
            print("FAIL  " + p)
        return 1
    print("OK    profile is consistent with the pack")
    return 0


if __name__ == "__main__":
    sys.exit(main())
