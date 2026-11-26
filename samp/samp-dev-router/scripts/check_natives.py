#!/usr/bin/env python3
"""Flag identifiers in code blocks that look like natives but are not declared anywhere we pin."""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
ASSETS = pathlib.Path(__file__).resolve().parents[1] / "assets"
known = set((ASSETS / "omp_natives.txt").read_text().split())
known |= set((ASSETS / "plugin_natives.txt").read_text().split())
known |= set((ASSETS / "helpers.txt").read_text().split())
known |= {"Text", "PlayerText", "bool", "Float", "WEAPON", "Dialog", "DB", "BitStream"}

IDENT = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\s*\(")
DECL = re.compile(r"\b(?:stock|native|forward|public)\s+[A-Za-z_][A-Za-z0-9_]*\s*([A-Za-z_][A-Za-z0-9_]*)?\s*\(")
DEFINED = re.compile(r"\b(?:stock|forward|public)\s+(?:[A-Za-z_][A-Za-z0-9_]*\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*\(")

def main() -> int:
    unknown = {}
    for path in sorted(ROOT.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        blocks = re.findall(r"```pawn\n(.*?)```", text, re.S)
        code = "\n".join(blocks)
        local = {m.group(1) for m in DEFINED.finditer(code)}
        for m in IDENT.finditer(code):
            name = m.group(1)
            if name in known or name in local:
                continue
            unknown.setdefault(path.parent.name, set()).add(name)
    total = sum(len(v) for v in unknown.values())
    print(f"{len(unknown)} skills, {total} unknown identifiers")
    for skill, names in sorted(unknown.items()):
        print(f"  {skill}: " + ", ".join(sorted(names)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
