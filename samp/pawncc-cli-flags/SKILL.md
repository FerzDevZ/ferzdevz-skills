---
name: pawncc-cli-flags
description: Use when a Pawn build needs the right pawncc flags.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, compiler]
    category: samp
---

# pawncc flags that matter

## When to Use

- A script compiles on one machine and fails on another, or CI and the desktop disagree.
- You need stack traces with file and line numbers, which only happen with `-d3`.
- The build must be strict (`-;+`, `-(+`) so code ports between SA-MP and open.mp without surprise.
- You are writing a Makefile or GitHub Action and want the flags recorded once.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Compiler | `pawncc` 3.10.10 (pawn-lang) | banner reads `Pawn compiler 3.10.10  Copyright (c) 1997-2006, ITB CompuPhase` |
| Default debug level | `-d1` | run-time checks, no symbolic information |
| `-d0` / `-d1` / `-d2` / `-d3` | none / checks / full / full + symbols | `-d3` is documented as "same as -d2, but implies -O0" |
| Default optimisation | `-O1` | `-O0` none, `-O2` full optimisations |
| Strict syntax | `-;+` and `-(+` | semicolon and parenthesis requirements, both default off |
| Compatibility | `-Z+` | older AMX behaviour for legacy servers |
| Escapes | `-\` | accept `\` as escape character in strings |
| Warnings | `-E` | turn warnings into errors |
| Include path | `-i<dir>` | the directory that holds `open.mp.inc`, not the folder above it |

## Production Implementation

1. Print the option table from the binary you will ship, never from a blog post:

```bash
pawncc 2>&1 | sed -n '1,45p'
```

2. Baseline open.mp build. Note the quoting: `-;+` and `-(+` are shell metacharacters and must be
   quoted in a shell, while a build tool that passes argv directly does not need quotes:

```bash
pawncc -i./includes -d3 -O2 '-;+' '-(+' -ogamemodes/main.amx gamemodes/main.pwn
```

3. Choose the level on purpose. `-d3` implies `-O0`, so a debug build is slow on purpose. Keep the
   two builds separate and never benchmark a `-d3` binary against production numbers:

```bash
pawncc -i./includes -d1 -O2 -ogamemodes/main.amx gamemodes/main.pwn   # release
pawncc -i./includes -d3     -ogamemodes/main.amx gamemodes/main.pwn   # crash reports
```

4. Pin one include root per target. `open.mp.inc` and `a_samp.inc` come from the open.mp include
   set; mixing a 0.3.7 `a_samp.inc` with open.mp includes produces duplicate natives at run time:

```bash
find / -maxdepth 6 -name 'open.mp.inc' 2>/dev/null | head -3
```

5. Fail CI on the first warning, then silence only what you have judged harmless by number:

```bash
set -o pipefail
pawncc -i./includes -d3 '-;+' '-(+' -E -ogamemodes/main.amx gamemodes/main.pwn | tee build.log
grep -E '[0-9]+ (Error|Warning)\.' build.log && exit 1 || exit 0
```

6. Size the abstract machine when the mode is large; the default stack/heap is 4096 cells:

```bash
pawncc -i./includes -d3 '-S8192' -XD65536 -ogamemodes/main.amx gamemodes/main.pwn
```

7. Keep the exact command in CI so a local pass is reproducible; a matrix entry that only changes
   the `-O` level documents itself in the diff:

```yaml
- name: Compile
  run: pawncc -i./includes -d3 '-;+' '-(+' -ogamemodes/main.amx gamemodes/main.pwn
```

8. Store the banner with the artifact: the compile log plus the first strings of the `.amx` prove
   which compiler produced a binary during an incident:

```bash
strings gamemodes/main.amx | head -2
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `bash: syntax error near unexpected token '('` | unquoted `-(+` | quote `-(+` and `-;+`, or call pawncc from make/argv |
| `fatal error 100: cannot read from file: "open.mp"` | `-i` points one level too high or too low | `-i` the directory that literally contains `open.mp.inc` |
| Server logs `File is for a newer version of the AMX` | compiler newer than the server's Pawn component | compile with the pawncc shipped for that server release |
| CI fails on `warning 203: symbol is never used` | `-E` plus dead code | delete the symbol or add `-w203` for that file only |
| Crash log shows addresses but no `file.pwn:line` | built with `-d1`/`-d2` | rebuild with `-d3` and keep symbols in the deployed `.amx` |
| Benchmarks show the server slower than expected | the "release" build actually used `-d3` | measure a `-O2` build without `-d3` |

## Verification

```bash
pawncc -i./includes -d3 '-;+' '-(+' -ogamemodes/main.amx gamemodes/main.pwn; echo "exit=$?"
test -s gamemodes/main.amx && echo "amx written"
```

Expected output:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            264 bytes
Code size:               72 bytes
Data size:               28 bytes
Stack/heap size:      16384 bytes; estimated max. usage=73 cells (292 bytes)
Total requirements:   16748 bytes
exit=0
amx written
```

## Sources (2026)

- https://github.com/pawn-lang/compiler
- https://www.compuphase.com/pawn/pawn.htm
- https://open.mp/docs/scripting/language/reference/Appendices
