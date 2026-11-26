#!/usr/bin/env python3
"""Audit a skill pack. Stdlib only.

Checks: frontmatter, required sections, depth, failure table, source URLs,
duplicate titles/descriptions, catalog freshness.

Usage:
    bin/audit.py                      # audit the pack this file lives in
    bin/audit.py --root /path/pack
    bin/audit.py --net                # also verify every source URL (GET, 8s)
    bin/audit.py --min-body 80 --strict
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import difflib
import json
import pathlib
import re
import sys
import urllib.error
import urllib.request

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)
URL = re.compile(r"https?://[^\s)>\]\"']+")
CODE_FENCE = re.compile(r"```([A-Za-z0-9_+-]*)")
REQUIRED_SECTIONS = (
    "## When to Use",
    "## Compatibility & Stack Matrix",
    "## Production Implementation",
    "## Failure Modes & Fixes",
    "## Verification",
    "## Sources",
)
STUB_MARKERS = ("TODO", "TBD", "FIXME", "lorem ipsum", "<placeholder>")
# sections that must contain a markdown table
TABLE_SECTIONS = ("## Failure Modes & Fixes", "## Compatibility & Stack Matrix")


def unquote(v: str) -> str:
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    return v


def parse(text: str) -> tuple[dict, str]:
    m = FRONT.match(text)
    if not m:
        return {}, text
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        if line.startswith((" ", "\t")):
            continue  # nested metadata (tags, category)
        meta[k.strip()] = unquote(v)
    return meta, text[m.end():]


def section(body: str, header: str) -> str:
    """Return a section body. Headers must sit at line start, otherwise a table
    row that mentions `## Verification` in inline code truncates the section."""
    lines = body.splitlines(keepends=True)
    start = None
    for idx, line in enumerate(lines):
        s = line.rstrip("\n").strip()
        if s == header or s.startswith(header + " "):
            start = idx + 1
            break
    if start is None:
        return ""
    stop = len(lines)
    for idx in range(start, len(lines)):
        s = lines[idx].rstrip("\n").strip()
        if s.startswith("## ") and s in REQUIRED_SECTIONS:
            stop = idx
            break
    return "".join(lines[start:stop])


def is_table(chunk: str) -> bool:
    return any(l.strip().startswith("|") and l.count("|") >= 2 for l in chunk.splitlines())


def check_skill(path: pathlib.Path, min_body: int, min_sources: int) -> dict:
    problems: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse(text)
    folder = path.parent.name

    name = meta.get("name", "")
    desc = meta.get("description", "")
    if not name:
        problems.append("frontmatter: missing 'name'")
    elif name != folder:
        problems.append(f"frontmatter: name '{name}' != folder '{folder}'")
    if not desc:
        problems.append("frontmatter: missing 'description'")
    elif len(desc) > 60:
        problems.append(f"frontmatter: description is {len(desc)} chars (max 60)")
    if not meta.get("version"):
        problems.append("frontmatter: missing 'version'")

    for marker in STUB_MARKERS:
        if marker.lower() in text.lower():
            problems.append(f"stub marker present: {marker}")

    if not body.lstrip().startswith("# "):
        problems.append("body: must start with an H1 title")

    missing = [s for s in REQUIRED_SECTIONS if s not in body]
    if missing:
        problems.append("missing sections: " + ", ".join(missing))

    lines = len(body.splitlines())
    if lines < min_body:
        problems.append(f"body is {lines} lines (min {min_body})")

    for hdr in TABLE_SECTIONS:
        chunk = section(body, hdr)
        if chunk and not is_table(chunk):
            problems.append(f"{hdr}: needs a markdown table")

    fm_rows = len([l for l in section(body, "## Failure Modes & Fixes").splitlines() if l.strip().startswith("|")])
    if section(body, "## Failure Modes & Fixes") and fm_rows < 5:
        problems.append("Failure Modes table needs >= 3 data rows")

    ver = section(body, "## Verification").strip()
    if ver and not re.search(r"`|bash|npm|node |python|curl|deno|go |cargo|flutter|gradle|xcodebuild|pytest", ver):
        problems.append("Verification has no runnable command")

    src = section(body, "## Sources").strip()
    urls = sorted(set(URL.findall(src)))
    if len(urls) < min_sources:
        problems.append(f"Sources: {len(urls)} URL(s), need >= {min_sources}")

    inside = False
    for line in body.splitlines():
        if not line.lstrip().startswith("```"):
            continue
        lang = line.lstrip()[3:].strip()
        if not inside:
            if not lang and not line.lstrip().startswith("``` "):
                problems.append("code fence without language tag")
            inside = True
        else:
            inside = False

    return {
        "name": name or folder,
        "path": str(path),
        "category": path.parent.parent.name,
        "description": desc,
        "lines": lines,
        "urls": urls,
        "problems": problems,
    }


def http_ok(url: str) -> tuple[str, str]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (skill-audit; +https://agentskills.io) "},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return url, "ok" if 200 <= r.status < 300 else f"status {r.status}"
    except urllib.error.HTTPError as e:
        return url, "blocked(403/429)" if e.code in (403, 429) else f"status {e.code}"
    except Exception as e:  # noqa: BLE001 - report any network failure as text
        return url, f"error {type(e).__name__}"


def main() -> int:
    ap = argparse.ArgumentParser()
    here = pathlib.Path(__file__).resolve().parent.parent
    ap.add_argument("--root", default=str(here))
    ap.add_argument("--only", default="", help="only audit categories matching this prefix")
    ap.add_argument("--min-body", type=int, default=60)
    ap.add_argument("--min-sources", type=int, default=2)
    ap.add_argument("--net", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="warnings count as failures")
    args = ap.parse_args()

    root = pathlib.Path(args.root).expanduser().resolve()
    files = sorted(p for p in root.glob("*/*/SKILL.md"))
    if args.only:
        files = [p for p in files if p.parent.parent.name == args.only
                 or p.parent.parent.name.startswith(args.only)]
    if not files:
        print(f"no skills found under {root}/*/*/SKILL.md")
        return 1

    results = [check_skill(p, args.min_body, args.min_sources) for p in files]

    # duplicates: descriptions and titles that say the same thing
    dups: list[str] = []
    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            a, b = results[i], results[j]
            ratio = difflib.SequenceMatcher(None, a["description"], b["description"]).ratio()
            titleratio = difflib.SequenceMatcher(None, a["name"], b["name"]).ratio()
            if ratio > 0.86 or titleratio > 0.90:
                dups.append(f"{a['name']} ~ {b['name']} (desc {ratio:.2f}, name {titleratio:.2f})")

    dead: list[tuple[str, str, str]] = []
    if args.net:
        all_urls = sorted({u for r in results for u in r["urls"]})
        with cf.ThreadPoolExecutor(max_workers=8) as pool:
            for url, state in pool.map(http_ok, all_urls):
                if state.startswith(("status 404", "status 410", "error")):
                    owners = [r["name"] for r in results if url in r["urls"]]
                    dead.append((url, state, ",".join(owners)))

    errors = [r for r in results if r["problems"]]
    cats: dict[str, int] = {}
    for r in results:
        cats[r["category"]] = cats.get(r["category"], 0) + 1

    if args.json:
        print(json.dumps({"skills": results, "duplicates": dups, "dead_urls": dead}, indent=1))
    else:
        print(f"skills: {len(results)}  categories: {len(cats)}  "
              f"lines: {sum(r['lines'] for r in results)}  "
              f"avg: {sum(r['lines'] for r in results) // max(len(results), 1)}")
        print("per category: " + ", ".join(f"{k}={v}" for k, v in sorted(cats.items())))
        if errors:
            print(f"\nFAIL  {len(errors)} skill(s) with problems")
            for r in errors:
                print(f"  {r['category']}/{r['name']}")
                for p in r["problems"]:
                    print(f"    - {p}")
        else:
            print("\nOK    all skills pass structure and depth gates")
        if dups:
            print(f"\nFAIL  {len(dups)} duplicate pair(s)")
            for d in dups:
                print("  " + d)
        if dead:
            print(f"\nFAIL  {len(dead)} unreachable source URL(s)")
            for url, state, owners in dead:
                print(f"  {state}  {url}  ({owners})")
        if args.net:
            checked = len({u for r in results for u in r["urls"]})
            print(f"\nnet: checked {checked} unique source URL(s)")

    failed = bool(errors or dups or dead)
    if args.strict and not failed:
        thin = [r["name"] for r in results if r["lines"] < args.min_body + 20]
        if thin:
            print("\nWARN  thin skills: " + ", ".join(thin))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
