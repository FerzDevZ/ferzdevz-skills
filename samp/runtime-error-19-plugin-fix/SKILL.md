---
name: runtime-error-19-plugin-fix
description: Use when a script dies with run time error 19.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash]
    category: samp
---

# run time error 19: file or function is not found

## When to Use

- A mode refuses to start with `Run time error 19: "File or function is not found"` (SA-MP) or
  `[Error] Function not registered: <native>` followed by `[Error] File or function is not found`
  (open.mp 1.6.x).
- A native worked on the developer box and is missing after a migration, a recompile, or a host move.
- A plugin is present in `plugins/` but the log shows fewer plugins loaded than expected.
- You need to prove which side is missing: the script's `native` declaration or the binary.

## Compatibility & Stack Matrix (2026)

| Component | Where it lives (open.mp 1.6.x) | Legacy equivalent |
| --- | --- | --- |
| Script list | `pawn.main_scripts`, `pawn.side_scripts` in `config.json` | `gamemode0`, `filterscripts` |
| Plugin binaries | `plugins/*.so` (Linux) / `*.dll` (Windows) | `plugins` line in `server.cfg` |
| Plugin registration | `pawn.legacy_plugins: ["crashdetect"]` | `plugins crashdetect.so` |
| Native provider | component in `components/` (e.g. `Databases.so`) | separate plugin |
| Architecture | 32-bit i386 only — AMX and every plugin | same |
| Include file | must match the binary's version | same |

## Production Implementation

1. Read the exact error line first. open.mp names the native, which is faster than guessing:

```bash
grep -nE 'Function not registered|Run time error 19|File or function is not found' log.txt
```

2. Native declaration check — list every native the script declares itself. Natives coming from an
   include are not listed here; the ones that are must be provided by a loaded plugin or component:

```bash
grep -nE '^[[:space:]]*native[[:space:]]' gamemodes/main.pwn
```

3. For each name from step 2, find the include that should declare it, and compare the two:

```bash
grep -rn "native .*MissingNativeThing" includes/ plugins/*/*.inc
```

4. Plugin binary presence check — the file must exist, be 32-bit, and have its dependencies
   resolvable. A 64-bit `.so` or a missing `libstdc++` looks exactly like a missing native:

```bash
ls -l plugins/ && file plugins/*.so
```

5. If the binary exists, check the loader's view and that it is an AMX plugin at all:

```bash
ldd plugins/streamer.so | grep 'not found'
nm -D --defined-only plugins/streamer.so | grep -c AmxLoad
```

6. Confirm the server was told to load it, and that it did:

```bash
grep -n 'legacy_plugins' -A4 config.json
grep -n 'Loading plugin' log.txt
```

7. Fix the smallest thing that is actually wrong: install the binary, correct the config entry, or
   recompile against the `.inc` that ships with the installed plugin version. Never hand-declare a
   native in the gamemode to "make it compile" — that just moves error 19 to run time.

8. Prefer a component when open.mp ships one (MySQL → `Databases.so`, custom models →
   `CustomModels.so`). Components are loaded from `components/` automatically and cannot drift from
   their `.inc` the way a legacy plugin can.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Loaded 0 plugins.` then error 19 | `plugins`/`legacy_plugins` entry missing or misspelled | add the bare name (`streamer`) and restart |
| Error only on Linux | Windows `.dll` copied to the host | install the `.so` build of the same version |
| Plugin loads, native still missing | `.inc` newer than the binary | recompile with the matching `.inc` or upgrade the binary |
| `ldd` prints `not found` | missing 32-bit runtime (`libstdc++.so.6`) | install `lib32stdc++6` / `gcc-multilib` |
| `file` says `ELF 64-bit` | 64-bit build on a 32-bit AMX host | replace with the i386 build |
| Works after `changemode` but not at boot | plugin listed after the script loads | put the plugin first in the list / fix the component order |

## Verification

```bash
./omp-server & sleep 6
grep -cE 'Function not registered|File or function is not found' log.txt
grep -nE 'Loading plugin|booted' log.txt
kill %1
```

Expected output — zero missing natives and the mode's first `print`:

```text
0
[Info] Loading plugin: crashdetect
[Info]   CrashDetect plugin 4.21
[Info] booted
```

## Sources (2026)

- https://open.mp/docs/server/config.json
- https://open.mp/docs/server/CommonServerIssues
- https://forum.open.mp/showthread.php?tid=1584
