---
name: crashdetect-stacktrace-parser
description: Use when crashdetect prints a stack you must fix.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash]
    category: samp
---

# crashdetect stack traces

## When to Use

- The server dies and `log.txt` has an `AMX backtrace` or `Native backtrace` you cannot read.
- A `Run time error N` points at a native and you need the caller in your own script.
- You must turn a repeat-offender crash into a single fixed line of Pawn instead of a guess.
- You want a signature you can count over time so a fix is provable, not anecdotal.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Plugin | CrashDetect 4.x (`crashdetect.so` / `crashdetect.dll`) | banner prints `CrashDetect plugin 4.21` |
| Load order | before every other plugin | otherwise it logs `CrashDetect must be loaded before '<plugin>'` |
| Script build | `-d3` | without symbols you get addresses, not `file.pwn:line` |
| Config | read from `server.cfg` at plugin load | yes, even on open.mp — restart to apply |
| Verbose mode | `trace pfn` | `n` natives, `p` publics, `f` normal functions |
| Slow-call warning | `long_call_time <us>` | default 5000 (5 ms), `0` disables |
| Output file | `crashdetect_log <name>` | default: the server log |

## Production Implementation

1. Install it where the server will load it and compile with symbols:

```bash
cp crashdetect.so plugins/ && grep -n 'legacy_plugins' -A3 config.json
pawncc -i./includes -d3 -ogamemodes/main.amx gamemodes/main.pwn
```

2. Keep settings in `server.cfg` — CrashDetect reads its cvars there at plugin load, not from
   `config.json`. Start narrow, widen only while chasing one call:

```ini
plugins crashdetect.so
crashdetect_log crashdetect.log
long_call_time 20000
trace_filter playerid=0
```

3. Turn tracing on for one public function at a time. Tracing every call on a busy server multiplies
   log size and hides the signal:

```bash
sed -i 's/^trace_filter.*/trace_filter OnPlayerCommandText/' server.cfg
```

4. Read the trace top-down and stop at the first frame that belongs to your `.amx`. Frames above it
   are natives (` crashdetect_PrintBacktrace`, `strlen`) that only carry the bad input:

```text
[debug] Run time error 4: "Array index out of bounds"
[debug] AMX backtrace:
[debug] #0 00002c4c in public OnPlayerCommandText (playerid=0, cmdtext[]="give 999") at gamemodes/main.pwn:812
[debug] #1 00001b34 in public OnPlayerUpdate (playerid=0) at gamemodes/main.pwn:233
```

5. Extract that frame mechanically instead of eyeballing a 4000-line log:

```bash
awk '/AMX backtrace/{f=1;next} f && /in (public|stock|static)? ?[A-Za-z_]+ /{print;exit}' log.txt
```

6. Count the signature before and after the fix — same file:line means the same bug:

```bash
awk '/AMX backtrace/{getline; print}' log.txt | sort | uniq -c | sort -rn | head
```

7. Fix at the caller, not at the native. `error 4` means an index; guard the index where it is
   computed, and validate the command text before it reaches the array.

8. Keep CrashDetect off the production fleet. The plugin's own README states it disables some
   runtime optimisations and slows the server; run it on staging, or load it on production only for
   the duration of a hunt, then remove it.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Trace shows only hex addresses | script built with `-d1`/`-d2` | rebuild with `-d3`, redeploy the `.amx` |
| `CrashDetect must be loaded before '<plugin>'` | plugin order | move `crashdetect` to the first entry |
| No `[debug]` lines at all | plugin not loaded, or `crashdetect_log` points elsewhere | `grep 'Loading plugin' log.txt`, then read that file |
| Server runs slow while tracing | `trace pfn` on a live server | narrow to one public, or stop tracing |
| The top frame is a native | reading the stack backwards | start at the first frame in your own `.amx` |
| `Long callback execution detected` | one callback over `long_call_time` | raise the threshold, then fix the hot callback |

## Verification

```bash
printf '%s\n' '[debug] Run time error 4: "Array index out of bounds"' \
  '[debug] AMX backtrace:' \
  '[debug] #0 00002c4c in public OnPlayerCommandText (playerid=0, cmdtext[]="give 999") at gamemodes/main.pwn:812' \
  > /tmp/trace.log
awk '/AMX backtrace/{f=1;next} f && /in public/{print;exit}' /tmp/trace.log
```

Expected output — the first in-script frame, which is the line you patch:

```text
[debug] #0 00002c4c in public OnPlayerCommandText (playerid=0, cmdtext[]="give 999") at gamemodes/main.pwn:812
```

## Sources (2026)

- https://github.com/AmyrAhmady/samp-plugin-crashdetect
- https://github.com/AmyrAhmady/samp-plugin-crashdetect/wiki/Compiling-scripts-with-debug-info
- https://open.mp/docs/server/CommonServerIssues
