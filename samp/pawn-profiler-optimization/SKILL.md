---
name: pawn-profiler-optimization
description: Use when CPU is high and you must prove which Pawn function.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, profiling, performance, amx]
    category: samp
---

# Profile Pawn before you rewrite it

## When to Use

- The server saturates a core at 100+ players and nobody can name the hot callback.
- A rewrite "felt faster" and you need numbers before and after.
- `OnPlayerUpdate` is the suspected cost but you have not measured it.
- You need per-function call counts, not just a tick rate.
- Not for leaks that survive a restart; that is `memory-leak-timer-audit`.

## Compatibility & Stack Matrix (2026)

| Instrument | What it gives you | Cost while enabled | Output |
| --- | --- | --- | --- |
| `profiler` plugin (Zeex 2.15.3, BSD-2) | per-function call count, total and self time, optional call graph | instrumented AMX, expect a large slowdown | `<amx>-profile.html` next to the AMX |
| `profiler_outputformat` | `html` (default), `xml`, `txt` | none | same file, different writer |
| `pawncc -d3` | function and line symbols inside the AMX | AMX size only, no runtime cost | what the profiler and crashdetect read |
| `pawncc -O1` / `-O2` | optimised bytecode | none | keep it on; `-d3` still works |
| `GetServerTickRate()` | server ticks per second | free | your own log |
| `GetTickCount()` around a block | wall time of one code path | free | your own log |
| `profiler_gamemodes` / `profile_gamemode 1` | which AMX gets attached | none | server.log line `Attached profiler to ...` |

## Production Implementation

1. Rebuild with symbols. The profiler reports addresses and `?` names without debug info, which makes the
   report useless:

```bash
pawncc gamemodes/rp.pwn -iinclude -d3 -O1 -ogamemodes/rp.amx
echo "exit=$?"
```

2. Register the plugin and its settings. The plugin parses `server.cfg` with its own reader, so these keys
   go in `server.cfg` even when the rest of the server runs from `config.json`:

```ini
; server.cfg - read by the profiler plugin itself, not by open.mp
profiler_gamemodes rp
profiler_outputformat html
profiler_callgraph 1
profiler_callgraphformat dot
```

```json
{
  "pawn": { "main_scripts": ["rp 1"], "legacy_plugins": ["profiler.so"] }
}
```

3. Open a fixed window from script so the sample has a known start and end. These are the natives the
   2.15.3 `profiler.inc` declares; some forks name the dump `Profiler_Write`, so read the include you ship:

```pawn
enum ProfilerState {
    PROFILER_DISABLED, PROFILER_ATTACHING, PROFILER_ATTACHED,
    PROFILER_STARTING, PROFILER_STARTED, PROFILER_STOPPING, PROFILER_STOPPED
};
native ProfilerState:Profiler_GetState();
native Profiler_Start();
native Profiler_Stop();
native Profiler_Dump();

forward ProfileStop();

stock bool:ProfileWindow(seconds)
{
    new ProfilerState:state = Profiler_GetState();
    if (state != PROFILER_ATTACHED && state != PROFILER_STOPPED)
    {
        printf("[profile] not attached (state=%d) - using tick logging", _:state);
        return false;
    }
    Profiler_Start();
    SetTimer("ProfileStop", seconds * 1000, false);
    return true;
}

public ProfileStop()
{
    Profiler_Stop();
    Profiler_Dump();
    printf("[profile] window closed at %d tick/s", GetServerTickRate());
    return 1;
}
```

4. Drive the same traffic you care about. A profiler window over an empty server only measures timers.

5. Read the report by total time first, then by call count. A function at 40 % total but 3 calls is a slow
   query; the same 40 % at 400,000 calls is a per-tick loop. Use the call graph when the top entry is a
   dispatcher and you need its callees.

6. Fix the shape, not the syntax. The usual finding is per-tick work over every player, and the usual fix is
   a timer plus a dirty flag:

```pawn
new g_Dirty[MAX_PLAYERS];
new g_LastHud[MAX_PLAYERS];

public OnPlayerUpdate(playerid)
{
    // only mark, never format
    if (GetPlayerMoney(playerid) != g_LastHud[playerid]) g_Dirty[playerid] = 1;
    return 1;
}

forward FlushHud();
public FlushHud()
{
    for (new playerid = 0, max = GetPlayerPoolSize(); playerid <= max; playerid++)
    {
        if (!g_Dirty[playerid]) continue;
        g_LastHud[playerid] = GetPlayerMoney(playerid);
        g_Dirty[playerid] = 0;
    }
    return 1;
}
```

7. Rebuild, re-run the identical window at the identical player count, and compare tick rate and the top
   five entries. Keep both reports; a diff of two HTML files is the only honest before/after.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| log says `Attached profiler to ... (no debug info)` | AMX compiled without `-d3` | rebuild with `-d3`, restart, re-attach |
| report lists hex addresses or `?` instead of names | same, symbols stripped | `-d3` plus a clean full rebuild, not an incremental one |
| no `-profile.html` after `Profiler_Dump()` | keys live in `server.cfg` and the server only has `config.json` | write the `profiler_*` keys into `server.cfg` |
| zero functions logged after 60 s | no players, so no callbacks ran | drive real traffic during the window |
| top entry is `OnPlayerUpdate` with time spread over many callees | rebuild state every tick instead of on change | timer plus dirty flag |
| profiler shows a fast server, production is slow | different player count or a different AMX | same count, same commit, at least 60 s |
| `Profiler_GetState()` stays `PROFILER_DISABLED` on open.mp | the legacy AMX hook did not attach in this build | fall back to `GetTickCount` instrumentation, keep the plugin out of production |

## Verification

```bash
grep -E "Attached profiler|Total function calls logged" server.log
ls -l gamemodes/*-profile.html
```

Expected output after a clean window: the attach line without `(no debug info)`, a call total in the
millions for a busy server, and one report file:

```text
[Info] Attached profiler to gamemodes/rp.amx
[Info] Total function calls logged: 4820113
-rw-r--r-- 1 omp omp 214633 Nov 26 12:04 gamemodes/rp-profile.html
```

## Sources (2026)

- https://github.com/sa-mp-kr/samp-plugin-profiler
- https://open.mp/docs/scripting/functions/GetServerTickRate
- https://open.mp/docs/server/config.json
