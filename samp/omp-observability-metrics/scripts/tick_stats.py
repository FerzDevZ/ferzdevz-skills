#!/usr/bin/env python3
"""Percentiles from lines like: metrics tick_avg_ms=12.40 players=48"""
import pathlib, re, statistics, sys

RX = re.compile(r"tick_avg_ms=([0-9.]+).*players=(\d+)")

def main(path: str) -> int:
    vals = [float(m.group(1)) for m in RX.finditer(pathlib.Path(path).read_text(errors="replace"))]
    if not vals:
        print("no metrics lines found")
        return 1
    vals.sort()
    p = lambda q: vals[min(len(vals) - 1, int(len(vals) * q))]
    print(f"samples={len(vals)} p50={p(.5):.2f} p95={p(.95):.2f} max={vals[-1]:.2f}")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "server_log.txt"))
