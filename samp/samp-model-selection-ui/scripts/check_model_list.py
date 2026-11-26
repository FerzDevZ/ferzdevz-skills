#!/usr/bin/env python3
"""Validate a model-selection list before it reaches the UI.

    python3 check_model_list.py scriptfiles/skins.txt
    python3 check_model_list.py --kind vehicles scriptfiles/cars.txt

Checks: every entry is an integer, in range for the kind, and not duplicated.
Exit 0 clean, 1 problems found, 2 bad usage / missing file.
"""
from __future__ import annotations

import pathlib
import sys

RANGES = {
    "skins": [(0, 311)],
    "vehicles": [(400, 611)],
}
CUSTOM_FROM = 20000  # 0.3.DL custom model ids start here; accepted as-is


def in_range(mid: int, kind: str) -> bool:
    if mid >= CUSTOM_FROM:
        return True
    return any(lo <= mid <= hi for lo, hi in RANGES[kind])


def main(argv: list[str]) -> int:
    kind = "skins"
    args = argv[1:]
    if args and args[0] == "--kind":
        if len(args) < 2 or args[1] not in RANGES:
            print(f"usage: {argv[0]} [--kind {'|'.join(RANGES)}] <list-file>")
            return 2
        kind, args = args[1], args[2:]
    if not args:
        print(f"usage: {argv[0]} [--kind {'|'.join(RANGES)}] <list-file>")
        return 2

    path = pathlib.Path(args[0])
    if not path.is_file():
        print(f"no such list file: {path}")
        return 2

    ids: list[int] = []
    bad: list[str] = []
    for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        line = line.split("//")[0].strip()
        if not line:
            continue
        try:
            mid = int(line)
        except ValueError:
            bad.append(f"line {n}: not a number ({line!r})")
            continue
        if not in_range(mid, kind):
            lo_hi = " / ".join(f"{lo}-{hi}" for lo, hi in RANGES[kind])
            bad.append(f"line {n}: {mid} outside {lo_hi} (or >= {CUSTOM_FROM})")
        ids.append(mid)

    dupes = sorted({i for i in ids if ids.count(i) > 1})
    print(f"{kind}: {len(ids)} models, {len(dupes)} duplicates, {len(bad)} problems")
    for b in bad[:10]:
        print("  -", b)
    for d in dupes[:10]:
        print(f"  - duplicate id {d}")
    return 1 if bad or dupes else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
