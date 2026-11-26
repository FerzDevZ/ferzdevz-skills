#!/usr/bin/env python3
"""Verify Pawn calls in skills against the pinned native allowlists. Stdlib only.

Fails when a call looks like a native (Set*, Get*, Is*, Create*, TextDraw*, Streamer_* …)
but is absent from samp/samp-dev-router/assets/ and not declared in the same skill.
Constants (ALL_CAPS) and clearly project-level helpers are reported as warnings.

    bin/check_natives.py                 # all skills
    bin/check_natives.py --only samp --names a,b
    bin/check_natives.py --json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ASSETS = ("samp/samp-dev-router/assets/omp_natives.txt",
          "samp/samp-dev-router/assets/plugin_natives.txt",
          "samp/samp-dev-router/assets/helpers.txt")

# a call starting with one of these reads as an API call, not a project helper
NATIVE_PREFIXES = ("Set", "Get", "Is", "Has", "Give", "Take", "Show", "Hide", "Create",
                   "Destroy", "Delete", "Add", "Remove", "Attach", "Detach", "Toggle",
                   "Enable", "Disable", "Send", "TextDraw", "PlayerTextDraw", "Select",
                   "Cancel", "Play", "Stop", "Pause", "Resume", "Kick", "Ban", "Unban",
                   "Block", "Allow", "Put", "Reset", "Update", "Apply", "Call")
PLUGIN_PREFIXES = ("Streamer_", "MySQL_", "DB_", "CACHE_", "ORM_", "FCNPC_", "MapAndreas_",
                   "ColAndreas_", "crashdetect_", "SSCANF_", "CallLocalFunction")
SQL_WORDS = {"VALUES", "SELECT", "INSERT", "UPDATE", "DELETE", "WHERE", "SET", "FROM"}

CALL = re.compile(r"\b([A-Z][A-Za-z0-9_]{2,})\s*\(")
DEF = re.compile(r"\b(?:stock|forward|public|native|hook|#define)\s+[\w:]*?\s*(\w+)\s*[\( ]")
ENUM_MEMBER = re.compile(r"^\s*(\w+)\s*(?:=|,)\s*$", re.M)
ARRAY = re.compile(r"^\s*(?:new|static)\s+\w*:?\s*(\w+)\s*\[", re.M)


def load_allowlists(root: pathlib.Path) -> set[str]:
    known: set[str] = set()
    for rel in ASSETS:
        p = root / rel
        if p.exists():
            known |= set(p.read_text().split())
    return known


def check(path: pathlib.Path, known: set[str]) -> tuple[list[str], list[str]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    code = "\n".join(re.findall(r"```pawn\n(.*?)```", text, re.S))
    defined = {m.group(1) for m in DEF.finditer(code)}
    defined |= {m.group(1) for m in ENUM_MEMBER.finditer(code)}
    defined |= {m.group(1) for m in ARRAY.finditer(code)}
    fail, warn = [], []
    for m in CALL.finditer(code):
        name = m.group(1)
        if name in known or name in defined or name in SQL_WORDS or name.isupper():
            continue
        if name.startswith(PLUGIN_PREFIXES):
            fail.append(name)
        elif name.startswith(NATIVE_PREFIXES):
            fail.append(name)
        else:
            warn.append(name)
    return sorted(set(fail)), sorted(set(warn))


def main() -> int:
    ap = argparse.ArgumentParser()
    root = pathlib.Path(__file__).resolve().parent.parent
    ap.add_argument("--root", default=str(root))
    ap.add_argument("--only", default="")
    ap.add_argument("--names", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    known = load_allowlists(root)
    if not known:
        print("no allowlists found under samp/samp-dev-router/assets/")
        return 1

    files = sorted(root.glob("*/*/SKILL.md"))
    if args.only:
        files = [p for p in files if p.parent.parent.name.startswith(args.only)]
    if args.names:
        wanted = {n.strip() for n in args.names.split(",") if n.strip()}
        files = [p for p in files if p.parent.name in wanted]

    failures, warnings = {}, {}
    for p in files:
        fail, warn = check(p, known)
        if fail:
            failures[p.parent.name] = fail
        if warn:
            warnings[p.parent.name] = warn

    if args.json:
        print(json.dumps({"unknown_calls": failures, "unverified_helpers": warnings}, indent=1))
    else:
        print(f"natives: {len(known)} allowlisted, {len(files)} skill(s) scanned")
        for name, calls in sorted(failures.items()):
            print(f"FAIL  samp/{name}: " + ", ".join(calls))
        for name, calls in sorted(warnings.items()):
            print(f"warn  samp/{name}: undeclared helper(s) " + ", ".join(calls))
        if not failures:
            print("OK    every API-looking call exists in the allowlist or is declared in-skill")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
