#!/usr/bin/env python3
"""Print the load order open.mp will use: $-prefixed first, recursive, alphabetical."""
import pathlib, sys

def main(root: str) -> int:
    base = pathlib.Path(root)
    if not base.is_dir():
        print(f"not a directory: {root}")
        return 2
    libs = [p for p in base.rglob("*") if p.suffix in {".so", ".dll", ".dylib"}]
    tier = lambda p: (0 if any(part.startswith("$") for part in p.parts) else 1, str(p))
    ordered = sorted(libs, key=tier)
    print(f"{len(ordered)} components in load order:")
    for p in ordered:
        mark = "$" if tier(p)[0] == 0 else " "
        print(f" {mark} {p.relative_to(base)}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "components"))
