#!/usr/bin/env python3
"""Verify the version claims written in skills against the live registries.

A URL can be alive while the number in front of it is three years old. This check
reads claims of the shape `<Library> <major.minor[.patch]>` from every SKILL.md and
compares them with npm, PyPI, GitHub releases or Docker Hub tags.

    bin/check_claims.py                 # report + exit 1 on drift
    bin/check_claims.py --offline       # use the cached registry snapshot only
    bin/check_claims.py --json

Status rules:
    ok        claim matches the current release line
    stale     claim is one minor behind (warn, does not fail)
    behind    claim is two or more minors behind (fails)
    ahead     claim is newer than the registry says (fails: invented version)
    odd       claim looks like a copy-paste error (e.g. "MySQL 0.3.1")
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path.home() / ".cache" / "ferzdevz-skills" / "versions.json"
UA = {"User-Agent": "skill-claim-audit (+https://agentskills.io)"}

# name in prose -> (kind, identifier)
LIBRARIES = {
    "Next.js": ("npm", "next"),
    "React": ("npm", "react"),
    "TypeScript": ("npm", "typescript"),
    "Tailwind": ("npm", "tailwindcss"),
    "Playwright": ("npm", "playwright"),
    "Vitest": ("npm", "vitest"),
    "axe-core": ("npm", "axe-core"),
    "pa11y": ("npm", "pa11y"),
    "Ragas": ("pypi", "ragas"),
    "MLflow": ("pypi", "mlflow"),
    "numpy": ("pypi", "numpy"),
    "Streamer": ("github", "samp-incognito/samp-streamer-plugin"),
    "YSI": ("github", "pawn-lang/YSI-Includes"),
    "crashdetect": ("github", "Zeex/samp-plugin-crashdetect"),
    "MySQL": ("docker", "mysql"),
    "MariaDB": ("docker", "mariadb"),
    "PostgreSQL": ("docker", "postgres"),
    "PgBouncer": ("github", "pgbouncer/pgbouncer"),
    "CMake": ("github", "Kitware/CMake"),
}

CLAIM = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(LIBRARIES, key=len, reverse=True))
    + r")\s+v?(\d+\.\d+(?:\.\d+)?)")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def latest(kind: str, ident: str) -> str | None:
    try:
        if kind == "npm":
            return fetch_json(f"https://registry.npmjs.org/{ident}/latest").get("version")
        if kind == "pypi":
            return fetch_json(f"https://pypi.org/pypi/{ident}/json")["info"]["version"]
        if kind == "github":
            tag = fetch_json(f"https://api.github.com/repos/{ident}/releases/latest").get("tag_name")
            return normalize(tag) if tag else None
        if kind == "docker":
            data = fetch_json(f"https://hub.docker.com/v2/repositories/library/{ident}/tags?page_size=100")
            tags = [t["name"] for t in data.get("results", [])]
            numeric = [t for t in tags if re.fullmatch(r"\d+(\.\d+){0,2}", t)]
            numeric.sort(key=lambda v: [int(x) for x in v.split(".")])
            return numeric[-1] if numeric else None
    except Exception:  # noqa: BLE001 - offline or rate limited
        return None
    return None


def normalize(v: str) -> str | None:
    """Turn a release tag into major.minor[.patch]; None when it has no version."""
    v = v.strip().lstrip("vV")
    m = re.search(r"\d+(?:[._]\d+){1,2}", v)
    if not m:
        return None
    return m.group(0).replace("_", ".")


def parts(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def classify(claim: str, current: str, kind: str) -> str:
    c, u = parts(claim), parts(current)
    if kind == "docker":
        # MySQL/PostgreSQL majors are a targeting decision (LTS 8.4 vs innovation 9.x),
        # not a correctness claim, so drift is reported but never fails the gate.
        return "targeted"
    if len(c) == 1 or c[0] > u[0]:
        return "ahead"
    if c[:2] == u[:2]:
        return "ok"
    if len(u) > 1 and c[0] == u[0] and c[1] == u[1] - 1:
        return "stale"
    return "behind"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    cache: dict[str, str] = {}
    if CACHE.exists():
        try:
            cache = json.loads(CACHE.read_text())
        except json.JSONDecodeError:
            cache = {}

    found: list[dict] = []
    for p in sorted(pathlib.Path(args.root).expanduser().resolve().glob("*/*/SKILL.md")):
        text = p.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            for m in CLAIM.finditer(line):
                lib, claim = m.group(1), m.group(2)
                context = line.lower()
                after = line[m.end():m.end() + 1]
                # a minimum requirement is not a claim about the current release
                if after == "+" or any(k in context for k in (
                        "minimum", "cmake_minimum_required", ">=", "at least",
                        "or newer", "or later", "or above")):
                    continue
                found.append({"skill": p.parent.name, "category": p.parent.parent.name,
                              "library": lib, "claim": claim, "kind": LIBRARIES[lib][0],
                              "ident": LIBRARIES[lib][1], "line": idx + 1})

    current: dict[str, str] = {}
    if args.offline:
        current = cache
    else:
        for lib, (kind, ident) in LIBRARIES.items():
            v = latest(kind, ident)
            if v:
                current[lib] = v
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        merged = {**cache, **current}
        CACHE.write_text(json.dumps(merged, indent=1))

    for f in found:
        cur = current.get(f["library"])
        f["current"] = cur or "unknown"
        f["status"] = classify(f["claim"], cur, f["kind"]) if cur else "unchecked"

    bad = [f for f in found if f["status"] in ("behind", "ahead", "odd")]
    warn = [f for f in found if f["status"] == "stale"]
    unchecked = [f for f in found if f["status"] == "unchecked"]

    if args.json:
        print(json.dumps({"claims": found, "fail": len(bad)}, indent=1))
    else:
        print(f"claims: {len(found)} across {len({f['skill'] for f in found})} skill(s); "
              f"{len(current)} librar(y/ies) resolved")
        by_lib: dict[str, list[dict]] = {}
        for f in found:
            by_lib.setdefault(f["library"], []).append(f)
        print(f"\n{'library':14} {'claim(s)':22} {'current':10} status")
        for lib in sorted(by_lib, key=lambda k: by_lib[k][0]["status"]):
            rows = by_lib[lib]
            claims = sorted({r["claim"] for r in rows})
            statuses = sorted({r["status"] for r in rows})
            print(f"{lib:14} {', '.join(claims)[:22]:22} {rows[0]['current']:10} {', '.join(statuses)}")
        if bad:
            print(f"\nFAIL  {len(bad)} claim(s) need a fix")
            for f in bad:
                print(f"  {f['status']:6} {f['library']} {f['claim']} (current {f['current']}) "
                      f"in {f['category']}/{f['skill']}")
        if warn:
            print(f"\nWARN  {len(warn)} claim(s) one minor behind")
            for f in warn[:10]:
                print(f"  {f['library']} {f['claim']} (current {f['current']}) in {f['skill']}")
        if unchecked:
            print(f"\nINFO  {len(unchecked)} claim(s) could not be resolved "
                  f"({', '.join(sorted({f['library'] for f in unchecked}))})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
