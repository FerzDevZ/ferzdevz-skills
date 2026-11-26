---
name: include-dependency-resolver
description: Use when pawncc cannot find an include that exists.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, compiler, build]
    category: samp
---

# Resolve Pawn includes deterministically

`fatal error 100: cannot read from file` means the compiler never looked where you think it looked.
Include resolution in pawncc is small enough to state exactly, and every rule below was reproduced
with the 3.10.10 compiler shipped by open.mp. Fix the search path, not the `#include` line.

## When to Use

- `fatal error 100: cannot read from file: "y_hooks"` although the file is on disk.
- The build works on one machine and fails on CI with the same files.
- Two libraries define the same symbol, or a global is redefined after an include moved.
- A vendored copy of a library sits next to the copy the package manager installed.
- YSI-style `#include <YSI_Coding\y_hooks>` fails on Linux but compiles on Windows.

## Compatibility & Stack Matrix (2026)

| Form | What pawncc actually does | Reproduced |
| --- | --- | --- |
| `-i<path>` | appends `path` to the include list; attach the path, no space | works, any number of flags |
| `-i <path>` | not a flag at all: `path` is read as an input file | `fatal error 100: cannot read from file: "./incB.p"` |
| `#include <name>` | searches the `-i` directories only, in flag order | a copy in the working directory is not found |
| `#include "name"` | searches the directory of the including file, then `-i` | file next to the source resolves, same file in cwd does not |
| Extension omitted | compiler appends `.inc` (then `.p`) | `<only>` resolved `only.inc` |
| Two copies on the path | the first `-i` directory containing the name wins | `#assert` proved which copy was seen |
| Letter case | exact match on Linux | `<DUP>` failed against `dup.inc` |
| Missing dependency | fatal error 100; failed compile-time check is fatal error 110 | both from the same compiler |

The order of `-i` flags is a priority list, and it is the only priority list. There is no implicit
search of the current directory, so a project that "works from the root" is relying on a flag it did
not notice. open.mp ships `open.mp.inc`, `omp_*.inc` and the legacy `a_*.inc` shims in one directory
(`omp-stdlib`); that directory is one entry in the list, not a default.

## Production Implementation

1. Put the include list in exactly one place in the build script, attached to the flag, and echo it.
   A path with a space after `-i` compiles the path as an input file and produces a confusing 100:

```bash
INC=(
  "-i$PWD/include"
  "-i$PWD/dependencies/YSI-Includes"
  "-i$HOME/samp-sdk/omp-stdlib"
)
printf 'INCLUDES: %s\n' "${INC[*]}"
"$HOME/samp-sdk/bin/pawncc" gamemodes/main.pwn "${INC[@]}" -o/tmp/main.amx -d3
```

2. Probe each dependency alone before blaming the gamemode. One include per probe turns "somewhere
   in the build" into a named file, and it fails fast on CI:

```bash
mkdir -p /tmp/probe && status=0
for inc in open.mp a_samp YSI_Coding/y_hooks streamer; do
  printf '#include <%s>\nmain() { return 0; }\n' "$inc" > /tmp/probe/one.pwn
  if ! "$HOME/samp-sdk/bin/pawncc" /tmp/probe/one.pwn "${INC[@]}" -o/tmp/probe/one.amx >/tmp/probe/out 2>&1; then
    echo "BROKEN include: $inc"; sed -n '1,3p' /tmp/probe/out; status=1
  fi
done
exit $status
```

3. Prove which copy wins instead of assuming. `#assert` runs at compile time and names the loser:

```bash
printf '#include <dup>\n#assert defined WHICH_A\nmain() { return 0; }\n' > /tmp/probe/order.pwn
"$HOME/samp-sdk/bin/pawncc" /tmp/probe/order.pwn -i/tmp/probe/incB -i/tmp/probe/incA -o/tmp/probe/o.amx
```

4. Hunt duplicate libraries by basename. Two copies of the same include with different content is the
   classic duplicate-symbol bug, and `-i` order only hides it:

```bash
find . -name '*.inc' -printf '%f %p\n' | sort | awk '{c[$1]++; p[$1]=p[$1]" "$2}
  END {for (f in c) if (c[f] > 1) print "DUP", f, p[f]}'
```

5. Keep one copy per library: package-managed dependencies in `dependencies/`, nothing vendored by
   hand, and the stdlib directory last so an accidental project file cannot shadow `open.mp.inc`
   once the duplicates are gone. Order cannot be both a safety net and a fix; remove the duplicate.

6. Normalise backslash includes. Linux treats `\` as a filename character, and Windows-only includes
   from YSI 5 era code fail with error 100 rather than a wrong-path message:

```bash
python3 - <<'PY'
import pathlib, re
inc = re.compile(r'(#include\s*<)([^>\n]*)(>)')
for p in list(pathlib.Path('.').rglob('*.inc')) + list(pathlib.Path('.').rglob('*.pwn')):
    t = p.read_text(encoding='utf-8', errors='replace')
    n = inc.sub(lambda m: m.group(1) + m.group(2).replace('\\', '/') + m.group(3), t)
    if n != t:
        p.write_text(n, encoding='utf-8')
        print('normalised', p)
PY
```

7. Fail the build on warnings that hide resolution problems (`-E` turns warnings into errors), so a
   shadowed function or redefined constant stops the job instead of shipping:

```bash
"$HOME/samp-sdk/bin/pawncc" gamemodes/main.pwn "${INC[@]}" -E -d3 -o/tmp/main.amx
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `fatal error 100 ... "./incB.p"` | `-i` written with a space before the path | attach it: `-i/tmp/probe/incB` |
| Include found in the editor, not in CI | Qawno adds its own include directory; the CI script does not | list every `-i` in the build script and log it |
| `#include <lib>` fails although `lib.inc` sits in the project root | angle brackets never search the working directory | add `-i$PWD` or switch to quotes for same-directory files |
| Quotes include works locally, fails after moving the file | quotes resolve against the including file's directory | keep quoted includes next to their source, or use `-i` |
| `<YSI_Core/y_hooks>` works, `<YSI_Core\y_hooks>` fails | backslash is not a path separator on Linux | convert to forward slashes |
| Duplicate symbol after adding a dependency | two copies of one library, different `-i` entries | delete the vendored copy, keep one directory |
| Same build passes on one box and fails on another | case difference in the include name | fix the case in the source, not the filesystem |

## Verification

```bash
mkdir -p /tmp/probe/incA /tmp/probe/incB
printf '#define WHICH_A\n' > /tmp/probe/incA/dup.inc
printf '#define WHICH_B\n' > /tmp/probe/incB/dup.inc
printf '#include <dup>\n#assert defined WHICH_B\nmain() { return 0; }\n' > /tmp/probe/order.pwn
"$HOME/samp-sdk/bin/pawncc" /tmp/probe/order.pwn -i/tmp/probe/incB -i/tmp/probe/incA -o/tmp/probe/o.amx
"$HOME/samp-sdk/bin/pawncc" /tmp/probe/order.pwn -i/tmp/probe/incA -i/tmp/probe/incB -o/tmp/probe/o2.amx
```

Expected: the first command prints `Done.`; the second prints
`order.pwn(2) : fatal error 110: assertion failed: defined WHICH_B` and aborts. Replacing the first
`-i` with `-i /tmp/probe/incB` must print `... fatal error 100: cannot read from file: "/tmp/probe/incB.p"`,
which is what a stray space looks like.

## Sources (2026)

- https://github.com/openmultiplayer/compiler/blob/master/readme_compuphase.txt
- https://open.mp/docs/scripting/language/reference/Appendices
- https://github.com/openmultiplayer/omp-stdlib
