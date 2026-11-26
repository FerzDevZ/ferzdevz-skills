#!/usr/bin/env python3
"""Validate a model-selection list: ids in range, no duplicates, sane size."""
import pathlib, sys

def main(path: str) -> int:
    ids, bad = [], []
    for n, line in enumerate(pathlib.Path(path).read_text().splitlines(), 1):
        line = line.split("//")[0].strip()
        if not line:
            continue
        try:
            mid = int(line)
        except ValueError:
            bad.append(f"line {n}: not a number ({line!r})")
            continue
        if not (0 <= mid <= 311 or 20001 <= mid <= 30000):
            bad.append(f"line {n}: {mid} outside 0-311 / 20001-30000")
        ids.append(mid)
    dupes = {i for i in ids if ids.count(i) > 1}
    print(f"{len(ids)} models, {len(dupes)} duplicates, {len(bad)} problems")
    for b in bad[:10]:
        print("  -", b)
    return 1 if bad or dupes else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "skins.txt"))
