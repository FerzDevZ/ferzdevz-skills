#!/usr/bin/env python3
"""Export the pack as a flat, installable tree plus a zip.

Flat layout is what most Agent Skills clients expect (`<name>/SKILL.md` at the top), while
this repo groups skills by category. The export keeps both readable:

    dist/skills/<name>/SKILL.md      flat tree, one folder per skill
    dist/ferzdevz-skills-<v>.zip     the same tree + CATALOG.md + README.md + LICENSE
    dist/SHA256SUMS                  checksums for both

    bin/export_pack.py --version 1.4.0
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import shutil
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
DIST = ROOT / "dist"


def sha256(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="dev")
    ap.add_argument("--keep", action="store_true", help="keep an existing dist/ tree")
    args = ap.parse_args()

    if DIST.exists() and not args.keep:
        shutil.rmtree(DIST)
    flat = DIST / "skills"
    flat.mkdir(parents=True, exist_ok=True)

    skills = sorted(ROOT.glob("*/*/SKILL.md"))
    names = [p.parent.name for p in skills]
    dupes = {n for n in names if names.count(n) > 1}
    if dupes:
        print("duplicate skill names, refusing to export: " + ", ".join(sorted(dupes)))
        return 1

    for p in skills:
        dst = flat / p.parent.name
        shutil.copytree(p.parent, dst)

    for extra in ("CATALOG.md", "README.md", "LICENSE", "PLANNING.md"):
        src = ROOT / extra
        if src.is_file():
            shutil.copy2(src, DIST / extra)

    zip_path = DIST / f"ferzdevz-skills-{args.version}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(flat.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(DIST))
        for extra in ("CATALOG.md", "README.md", "LICENSE", "PLANNING.md"):
            f = DIST / extra
            if f.is_file():
                z.write(f, extra)

    sums = DIST / "SHA256SUMS"
    sums.write_text(f"{sha256(zip_path)}  {zip_path.name}\n")

    print(f"exported {len(skills)} skills -> {flat}")
    print(f"archive: {zip_path} ({zip_path.stat().st_size // 1024} KiB)")
    print(sums.read_text().strip())
    return 0


if __name__ == "__main__":
    sys.exit(main())
