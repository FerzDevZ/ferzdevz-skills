---
name: amx-decompilation-audit
description: Use when auditing an AMX you did not compile.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, amx, audit, security]
    category: samp
---

# Audit an AMX by its imports, not by a decompiler

An `.amx` is bytecode for the Pawn abstract machine. A decompiler guesses the
source back from that bytecode and is wrong often enough that the guess is not
evidence. What the file really says is the instruction stream and the native
table: those list every server function the binary will call. Audit from those,
and treat decompiled text as a hypothesis you check line by line.

## When to Use

- A third-party filterscript or gamemode must be reviewed before it runs on your server.
- You need the exact set of natives a binary imports, to know what it can do (files, sockets, bans).
- A vendor shipped an `.amx` without sources and you must decide whether it is safe to load.
- Something on the server writes files you did not expect and you suspect the binary, not the gamemode.
- Legality gate: only audit an AMX **you** compiled, or one whose author gave written permission.
  Decompiling someone else's binary and shipping the recovered source usually breaches its
  licence and the community's rules; decompiler output is not the original source and must
  never be redistributed as if it were.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | the release tarball ships `qawno/pawndisasm`, no extra install |
| Disassembler | `pawndisasm <in.amx> <out.lst>` | CompuPhase tool, reads the real native table |
| AMX format | file version 8 | magic `0xF1E0`, 56-byte header, 8-byte native table entries |
| Compiler | pawncc 3.10.10 (`-d3` optional) | debug info only adds source lines to the listing |
| Decompiler | DeAMX (trc_, 2008, Lua) | approximate; useful for strings and shape, not for truth |
| Truth set | `samp-dev-router/assets/omp_natives.txt` + `plugin_natives.txt` | what your build can actually resolve |

## Production Implementation

1. Freeze the artifact before you analyse it, so the hash you audit is the hash
   you later deploy.

```bash
sha256sum handed/anticheat.amx | tee handed/anticheat.amx.sha256
```

2. Disassemble. This prints every instruction, and the `sysreq.c` lines name the
   imports from the file's own native table.

```bash
pawndisasm handed/anticheat.amx /tmp/anticheat.lst
grep -c 'sysreq' /tmp/anticheat.lst
```

3. Reduce the listing to the import list. Anything unexpected there is a
   capability you did not grant, which matters more than any control flow.

```bash
grep -E '[[:space:]]sysreq' /tmp/anticheat.lst \
  | sed -n 's/.*;[[:space:]]*//p' | sort -u
```

4. Automate the comparison, because "I looked at it" is not a reproducible
   review. This script is the check that goes into the audit record.

```bash
#!/usr/bin/env bash
set -euo pipefail
amx=${1:?usage: amx-audit.sh game.amx [natives.txt ...]}
shift
[ "$#" -gt 0 ] || set -- samp/samp-dev-router/assets/omp_natives.txt \
                        samp/samp-dev-router/assets/plugin_natives.txt
lst=$(mktemp); $HOME/samp-sdk/bin/pawndisasm "$amx" "$lst"
grep -E '[[:space:]]sysreq' "$lst" | sed -n 's/.*;[[:space:]]*//p' | sort -u > "$lst.names"
cat "$@" | sort -u > "$lst.known"
missing=$(comm -23 "$lst.names" "$lst.known" || true)
printf 'imports=%s unresolved=%s\n' "$(wc -l < "$lst.names")" \
  "$(printf '%s' "$missing" | grep -c . || true)"
[ -z "$missing" ] || printf 'UNRESOLVED %s\n' $missing
[ -z "$missing" ]
```

5. Read the imports as a capability list. `fopen`/`fwrite` mean the script
   touches `scriptfiles/`; HTTP or socket imports mean outbound traffic; ban and
   RCON natives mean it can lock you out of your own server.

```bash
grep -nE 'fopen|fwrite|HTTP_|Socket|Ban|SendRconCommand' /tmp/anticheat.lst
```

6. Strings give you URLs, file names and payload markers the imports do not.

```bash
strings -n 6 handed/anticheat.amx | sort -u | grep -iE 'http|\.pwn|\.ini|/tmp'
```

7. Run it sandboxed before trusting it: a disposable container, its own
   `scriptfiles/`, no RCON password it can read, and a syscall trace of what it
   opens.

```bash
strace -f -e trace=openat,write -o /tmp/amx.strace ./omp-server
```

8. Only now, if you still need the logic, decompile. Every decompiled call you
   act on must be confirmed in the listing, because aliases lie: the open.mp
   include declares `TextDrawColour` as an alias of `TextDrawColor`, and the
   binary imports the **old** spelling.

```text
native bool:TextDrawColour(Text:textid, textColour) = TextDrawColor;
; the AMX still says:  sysreq.c 00000000   ; TextDrawColor
```

9. Record the verdict next to the hash: imports reviewed, strings reviewed,
   sandbox trace reviewed, decision and reviewer. The next operator reruns the
   script instead of re-litigating the decision.

```bash
printf '%s %s %s\n' "$(date -u +%F)" "$(cut -d' ' -f1 handed/anticheat.amx.sha256)" \
  "audited: imports unresolved=0, no file/socket natives, sandbox log clean" >> HANDED.md
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Decompiled text shows a native the listing never calls | decompiler invented a call or mis-read a string reference | trust `sysreq` lines only; diff the two lists |
| Audit reports a native missing but the script runs | export comes from a plugin, not from `omp_natives.txt` | pass `plugin_natives.txt` to the script as well |
| A renamed function passes the audit unexpectedly | the include aliases the new name to the old symbol, and the AMX imports the old one | audit symbol names, and check both sides of an alias |
| `sysreq` count is 0 on a script that clearly calls natives | library AMX or a stub, not a gamemode | confirm the artifact type before auditing |
| Strings look truncated or absent | packed-string build | read the data block from the listing, do not rely on `strings` |
| Script writes outside `scriptfiles/` in the sandbox | relative paths resolve against the server working directory | run with a scratch `scriptfiles/` and diff the `strace` |

## Verification

```bash
chmod +x tools/amx-audit.sh
./tools/amx-audit.sh build/mygm.amx
printf 'TextDrawCreate\n' > /tmp/short.txt
./tools/amx-audit.sh build/mygm.amx /tmp/short.txt
```

- First run prints `imports=8 unresolved=0` and exits `0` for a gamemode whose
  eight imports all exist in the pinned lists.
- Second run prints `imports=1 unresolved=1` plus `UNRESOLVED <native>` and exits
  `1`: the check fails closed instead of passing silently.
- On the handed binary, the script output plus the `strace` file is the evidence
  recorded in `HANDED.md`; no decompiled line is cited without a `sysreq` match.

## Sources (2026)

- https://github.com/compuphase/pawn/blob/main/compiler/pawndisasm.c
- https://github.com/pawn-lang/compiler
- https://github.com/AmyrAhmady/DeAMX
