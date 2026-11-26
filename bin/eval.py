#!/usr/bin/env python3
"""Score an agent answer against a skill eval case. Stdlib only.

A case lives in evals/<case>/:
    prompt.md            the task given to the agent, unchanged between arms
    fixture/             files copied into the work dir before the agent starts
    graders/*.md         one check per file (see below)

Grader format (plain `key: value` lines, no YAML dependency):

    id: cookies-outside-leaf
    weight: 2
    path: app/layout.tsx
    must_match: Suspense
    must_not_match: cookies\\(

`path` is relative to the answer directory. All supplied conditions must hold.
Exit code 0 when every grader passes, 1 otherwise.

Usage:
    bin/eval.py list
    bin/eval.py lint                        # validate cases and graders (CI)
    bin/eval.py score --case <name> --dir <answer dir>
    bin/eval.py score --case <name> --dir <a> --compare <b>   # two arms side by side
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
EVALS = ROOT / "evals"
KEYS = ("id", "weight", "path", "must_match", "must_not_match", "note")


def parse_grader(p: pathlib.Path) -> dict:
    data: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"{p}: no colon in line {line!r}")
        k, v = line.split(":", 1)
        k = k.strip()
        if k not in KEYS:
            raise ValueError(f"{p}: unknown key {k!r}")
        data[k] = v.strip()
    if "id" not in data or "path" not in data:
        raise ValueError(f"{p}: needs id and path")
    if "must_match" not in data and "must_not_match" not in data:
        raise ValueError(f"{p}: needs must_match or must_not_match")
    return data


def load_case(name: str) -> tuple[pathlib.Path, list[dict]]:
    case = EVALS / name
    if not case.is_dir():
        raise SystemExit(f"no such case: {case}")
    graders = [parse_grader(g) for g in sorted((case / "graders").glob("*.md"))]
    if not graders:
        raise SystemExit(f"{case}: no graders")
    return case, graders


def resolve_path(answer: pathlib.Path, pattern: str) -> pathlib.Path | None:
    """Exact relative path first, then a glob: shallowest match wins, so an answer file
    at the top of the work dir beats a copy inside node_modules/ or build/."""
    direct = answer / pattern
    if direct.is_file():
        return direct
    name = pattern.split("/")[-1]
    matches = [p for p in answer.rglob(name) if p.is_file()]
    if not matches:
        return None
    matches.sort(key=lambda p: (len(p.relative_to(answer).parts), str(p)))
    tail = [seg for seg in pattern.split("/") if seg not in ("**", "*")]
    for m in matches:
        if m.relative_to(answer).as_posix().endswith("/".join(tail)):
            return m
    return matches[0]


def score(answer: pathlib.Path, graders: list[dict]) -> tuple[float, list[dict]]:
    results, total, earned = [], 0, 0.0
    for g in graders:
        weight = float(g.get("weight", "1"))
        total += weight
        target = resolve_path(answer, g["path"])
        text = target.read_text(encoding="utf-8", errors="replace") if target else ""
        ok = target is not None
        detail = f"found {target.relative_to(answer)}" if target else "file missing"
        if ok and "must_match" in g:
            hit = bool(re.search(g["must_match"], text, re.M))
            ok = ok and hit
            detail = ("matched" if hit else "pattern not found") + f": {g['must_match']}"
        if ok and "must_not_match" in g:
            hit = bool(re.search(g["must_not_match"], text, re.M))
            ok = ok and not hit
            detail = ("forbidden pattern absent" if not hit else "forbidden pattern present")
            detail += f": {g['must_not_match']}"
        earned += weight if ok else 0.0
        results.append({"id": g["id"], "path": g["path"], "weight": weight,
                        "pass": ok, "detail": detail})
    return (earned / total if total else 0.0), results


def print_score(name: str, label: str, pct: float, results: list[dict]) -> None:
    passed = sum(1 for r in results if r["pass"])
    print(f"\n{name} [{label}]  {passed}/{len(results)} graders, score {pct:.0%}")
    for r in results:
        mark = "PASS" if r["pass"] else "FAIL"
        print(f"  {mark} w{r['weight']:g} {r['id']} -> {r['detail']}")


def cmd_list() -> int:
    if not EVALS.is_dir():
        print("no evals/ directory")
        return 1
    for case in sorted(p for p in EVALS.iterdir() if (p / "graders").is_dir()):
        n = len(list((case / "graders").glob("*.md")))
        print(f"{case.name}: {n} graders, fixture={'yes' if (case / 'fixture').is_dir() else 'no'}")
    return 0


def cmd_lint() -> int:
    bad = 0
    cases = sorted(p for p in EVALS.iterdir() if p.is_dir()) if EVALS.is_dir() else []
    for case in cases:
        problems = []
        if not (case / "prompt.md").is_file():
            problems.append("missing prompt.md")
        gdir = case / "graders"
        graders = sorted(gdir.glob("*.md")) if gdir.is_dir() else []
        if not graders:
            problems.append("no graders")
        ids = set()
        for g in graders:
            try:
                data = parse_grader(g)
                for rx in ("must_match", "must_not_match"):
                    if rx in data:
                        re.compile(data[rx])
                if data["id"] in ids:
                    problems.append(f"duplicate grader id {data['id']}")
                ids.add(data["id"])
                if not re.fullmatch(r"[a-z0-9-]+", data["id"]):
                    problems.append(f"{g.name}: id must be lowercase-hyphen")
            except re.error as e:
                problems.append(f"{g.name}: bad regex ({e})")
            except ValueError as e:
                problems.append(str(e))
        if problems:
            bad += 1
            print(f"FAIL {case.name}")
            for p in problems:
                print("  -", p)
        else:
            print(f"ok   {case.name} ({len(graders)} graders)")
    if bad:
        print(f"\n{bad} case(s) invalid")
        return 1
    print(f"\nall {len(cases)} case(s) valid")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    sub.add_parser("lint")
    sp = sub.add_parser("score")
    sp.add_argument("--case", required=True)
    sp.add_argument("--dir", required=True)
    sp.add_argument("--compare", default="")
    sp.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "lint":
        return cmd_lint()

    name, graders = load_case(args.case)
    pct_a, res_a = score(pathlib.Path(args.dir).expanduser(), graders)
    out = {"case": name.name, "arms": [{"label": args.dir, "score": pct_a, "graders": res_a}]}
    if args.compare:
        pct_b, res_b = score(pathlib.Path(args.compare).expanduser(), graders)
        out["arms"].append({"label": args.compare, "score": pct_b, "graders": res_b})
    if args.json:
        print(json.dumps(out, indent=1))
    else:
        for arm in out["arms"]:
            print_score(name.name, arm["label"], arm["score"], arm["graders"])
        if len(out["arms"]) == 2:
            delta = out["arms"][1]["score"] - out["arms"][0]["score"]
            print(f"\ndelta (compare - dir): {delta:+.0%}")
    return 0 if all(a["score"] == 1.0 for a in out["arms"]) else 1


if __name__ == "__main__":
    sys.exit(main())
