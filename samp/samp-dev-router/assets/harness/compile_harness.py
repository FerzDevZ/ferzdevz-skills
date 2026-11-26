#!/usr/bin/env python3
"""Compile the representative gamemode and fail on any error or warning."""
import pathlib, re, subprocess, sys, tempfile

HERE = pathlib.Path(__file__).resolve().parent
PAWNCC = pathlib.Path.home() / "samp-sdk/bin/pawncc"
INC = pathlib.Path.home() / "samp-sdk/omp-stdlib"

def main() -> int:
    if not PAWNCC.exists():
        print("pawncc missing; skipped")
        return 0
    with tempfile.TemporaryDirectory() as td:
        out = pathlib.Path(td) / "harness.amx"
        r = subprocess.run([str(PAWNCC), f"-i{INC}", "-d3", "-;+", "-(+",
                            str(HERE / "harness.pwn"), f"-o{out}"],
                           capture_output=True, text=True)
        text = r.stdout + r.stderr
        problems = [l for l in text.splitlines() if re.search(r"(error|warning) \d+:", l)]
        if not out.exists() or problems:
            print(f"harness failed: {len(problems)} diagnostics")
            for p in problems[:12]:
                print("  " + p)
            return 1
    print("harness compiled: 0 errors, 0 warnings")
    return 0

if __name__ == "__main__":
    sys.exit(main())
