#!/usr/bin/env python3
"""Check that every #include used in a pawn block resolves against omp-stdlib.

Snippets are fragments: statements reference variables that only exist in a real gamemode,
so compiling them standalone reports context errors that are not defects. The one check
that is always meaningful is a missing include (fatal error 100), which would break the
snippet for every reader."""
import pathlib, re, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
PAWNCC = pathlib.Path.home() / "samp-sdk/bin/pawncc"
INCLUDES = pathlib.Path.home() / "samp-sdk/omp-stdlib"
MISSING = re.compile(r"fatal error 100: cannot read from file: \"([^\"]+)\"")

def main() -> int:
    if not PAWNCC.exists():
        print("pawncc missing; skipped")
        return 0
    bad, blocks = {}, 0
    for path in sorted(ROOT.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        for code in re.findall(r"```pawn\n(.*?)```", text, re.S):
            blocks += 1
            with tempfile.TemporaryDirectory() as td:
                src = pathlib.Path(td) / "s.pwn"
                src.write_text("#include <open.mp>\n" + code + "\n")
                r = subprocess.run([str(PAWNCC), f"-i{INCLUDES}", "-d0", str(src),
                                    f"-o{pathlib.Path(td) / 'o.amx'}"], capture_output=True, text=True)
                for inc in MISSING.findall(r.stdout + r.stderr):
                    if inc.startswith("YSI_"):
                        continue  # external package, resolved by sampctl, not omp-stdlib
                    if inc.endswith(".inc"):
                        bad.setdefault(path.parent.name, set()).add(inc)
    print(f"{blocks} pawn blocks, {len(bad)} skills with an include that does not resolve")
    for skill, incs in bad.items():
        print(f"  {skill}: " + ", ".join(sorted(incs)))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
