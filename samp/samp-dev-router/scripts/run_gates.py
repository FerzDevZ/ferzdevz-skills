#!/usr/bin/env python3
"""Run every library gate in order and summarise."""
import pathlib, subprocess, sys

HERE = pathlib.Path(__file__).resolve().parent
CHECKS = [
    ("structure", HERE / "validate_library.py"),
    ("natives", HERE / "check_natives.py"),
    ("includes", HERE / "compile_snippets.py"),
    ("harness", HERE.parent / "assets/harness/compile_harness.py"),
    ("catalog", HERE / "build_catalog.py"),
    ("versions", HERE / "check_versions.py"),
]

def main() -> int:
    failed = []
    for name, script in CHECKS:
        r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} {name}: {tail}")
        if r.returncode != 0:
            failed.append(name)
    print(("all gates green" if not failed else "failed: " + ", ".join(failed)))
    return 1 if failed else 0

if __name__ == "__main__":
    sys.exit(main())
