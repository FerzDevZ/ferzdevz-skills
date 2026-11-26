#!/usr/bin/env python3
"""Summarise crashdetect output: exception counts, top signatures, first script frame."""
import collections, pathlib, re, sys

ERR = re.compile(r"Run time error (\d+):\s*\"([^\"]+)\"")
FRAME = re.compile(r"#\d+\s+[0-9a-f]+ in (\S+) .* at (\S+):(\d+)")

def main(path: str) -> int:
    text = pathlib.Path(path).read_text(encoding="utf-8", errors="replace")
    errors = collections.Counter(ERR.findall(text))
    frames = FRAME.findall(text)
    print(f"exceptions: {sum(errors.values())}")
    for (code, msg), n in errors.most_common(10):
        print(f"  error {code} x{n}: {msg}")
    print("first script frame per exception block:")
    for fn, file, line in frames[:10]:
        if file.endswith((".pwn", ".inc")):
            print(f"  {file}:{line}  ({fn})")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "server_log.txt"))
