#!/usr/bin/env python3
"""Count actionable signatures per hour in an open.mp / SA-MP log."""
import collections, pathlib, re, sys

PATTERNS = {
    "runtime_error": re.compile(r"Run time error"),
    "exception": re.compile(r"Exception|SIGSEGV", re.I),
    "lost_connection": re.compile(r"Lost connection", re.I),
    "failed": re.compile(r"\bFailed\b"),
    "plugin": re.compile(r"plugin.*(fail|error)", re.I),
}

def main(path: str) -> int:
    text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    counts = collections.Counter()
    for line in text:
        for name, rx in PATTERNS.items():
            if rx.search(line):
                counts[name] += 1
    print(f"lines: {len(text)}")
    for name in PATTERNS:
        print(f"  {name}: {counts[name]}")
    actionable = counts["runtime_error"] + counts["exception"] + counts["plugin"]
    print("actionable:", actionable)
    return 1 if actionable else 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "server_log.txt"))
