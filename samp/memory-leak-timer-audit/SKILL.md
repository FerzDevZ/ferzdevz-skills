---
name: memory-leak-timer-audit
description: Use when timers or memory grow with server uptime.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, profiling]
    category: samp
---

# Memory and timer leak audit

On open.mp a leaked timer is cheap to prove: `CountRunningTimers()` reports the live total and
`IsValidTimer()` says whether a stored id still runs. Use those two before a heap profiler.

## When to Use

- RSS or the running-timer total steps up with uptime and never steps back down.
- Timers still fire after the player who started them disconnected.
- A soak test shows lag that a restart clears, and you need the object that grew.

## Compatibility & Stack Matrix (2026)

| Behaviour | open.mp 1.6.x | SA-MP 0.3.7-R2 |
| --- | --- | --- |
| Timer id range | starts at 1, ids never reused | ids can be reused once a timer ends |
| Invalid id | `INVALID_TIMER` is `0` (`-1` is a live-looking id) | same constant, no `IsValidTimer` |
| Live count | `CountRunningTimers()` since 1.1.0.2612 | count your own array |
| Enumerate | `GetRunningTimers()` | not available |
| Validity / kind | `IsValidTimer`, `IsRepeatingTimer` | not available |
| Remaining / interval | `GetTimerRemaining`, `GetTimerInterval` | not available |
| `SetTimerEx` specifiers | `i d a s f b` (arrays and strings allowed) | `a`/`s` unusable |
| Interval accuracy | accurate | roughly 25% off |
| `KillTimer` return | always `0` | always `0` |

Everything below is written against the open.mp column; the SA-MP column is what you get
when the same audit runs on a gamemode that has not migrated.

## Production Implementation

1. Print the two numbers the server already tracks, once a minute, on one timer:

```pawn
stock GetOnlineCount()
{
    new ids[MAX_PLAYERS];
    return GetPlayers(ids, sizeof(ids));
}

forward TimerWatch();
public TimerWatch()
{
    printf("WATCH timers=%d players=%d", CountRunningTimers(), GetOnlineCount());
    return 1;
}
```

2. Own every timer through one slot array, so a respawn replaces instead of stacking:

```pawn
#define PULSE_SLOTS 2
new g_PulseTimer[MAX_PLAYERS][PULSE_SLOTS];

stock StartPulse(playerid, slot)
{
    if (slot < 0 || slot >= PULSE_SLOTS) return 0;
    if (g_PulseTimer[playerid][slot]) KillTimer(g_PulseTimer[playerid][slot]);
    g_PulseTimer[playerid][slot] =
        SetTimerEx("OnPulse", 1000, true, "ii", playerid, slot);
    return 1;
}
```

3. Make the callback survive the player and stop rebuilding the frame. An id is not proof
   the slot still belongs to the same person, and `new buf[256]` is a full kilobyte of frame
   re-created sixty times a minute for every player; `static` keeps one copy:

```pawn
forward OnPulse(playerid, slot);
public OnPulse(playerid, slot)
{
    static line[160];
    if (!IsPlayerConnected(playerid)) return 0;
    format(line, sizeof(line), "PULSE player=%d slot=%d", playerid, slot);
    return 1;
}
```

4. Kill on every exit: disconnect, death, dialog close, gamemode exit. Reset the slot to `0`
   after the kill so the next start does not test a dead id:

```pawn
public OnPlayerDisconnect(playerid, reason)
{
    for (new s = 0; s < PULSE_SLOTS; s++)
    {
        if (IsValidTimer(g_PulseTimer[playerid][s])) KillTimer(g_PulseTimer[playerid][s]);
        g_PulseTimer[playerid][s] = 0;
    }
    return 1;
}
```

5. Read the growth curve instead of guessing. Sample RSS once a minute for an hour with zero
   players, and pair it with the timer total from the log — a flat RSS with a rising
   `timers=` means the leak is the timer table, not script memory:

```bash
pid=$(pgrep -f omp-server | head -1)
for i in $(seq 1 60); do printf '%s %s\n' "$(date -u +%H:%M)" "$(ps -o rss= -p "$pid")"; sleep 60; done > rss.log
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `timers=` climbs one per respawn | timer started in `OnPlayerSpawn`, killed only on disconnect | store the id per slot and kill before re-arming |
| `timers=` never returns to 0 on an empty server | global timer has no `OnGameModeExit` kill | kill it there and set the id to `0` |
| `KillTimer(-1)` kills nothing | `-1` is not `INVALID_TIMER`; ids start at 1 | test `IsValidTimer(id)` before killing |
| Callback writes to the wrong player | slot reused after reconnect, timer outlived its owner | `IsPlayerConnected` guard in the callback |
| RSS steps up with no timer growth | per-call `new buf[...]` in a hot callback | `static` buffer at function scope |
| CPU flat but `tick_rate` drops | 20-50 ms repeating timer per player | move to a 1 s batch that loops players once |
| Ghost iterator entries | add on connect, remove only on kick | remove in `OnPlayerDisconnect` for every path |

## Verification

Every start site should have a kill path. On a balanced tree the counts match:

```bash
grep -rn --include='*.pwn' -E '\bSetTimer(Ex)?\(' gamemodes/ | wc -l
grep -rn --include='*.pwn' -E '\bKillTimer\(' gamemodes/ | wc -l
```

```text
3
3
```

A gap names the file that starts a timer it never stops; `grep -rn -E 'SetTimer' gamemodes/`
against the kill sites finds the offender in one pass.

Runtime proof, with every player disconnected:

```bash
grep 'WATCH' log.txt | tail -3
```

```text
WATCH timers=3 players=0
WATCH timers=3 players=0
WATCH timers=3 players=0
```

The total is constant with `players=0`; the only remaining timers are the global ones you
can name. RSS over the same hour:

```bash
awk 'NR==1{f=$2} END{printf "first=%d last=%d drift=%.1f%%\n", f, $2, ($2-f)*100/f}' rss.log
```

```text
first=91340 last=91892 drift=0.6%
```

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetTimerEx
- https://open.mp/docs/scripting/functions/KillTimer
- https://open.mp/docs/scripting/functions/CountRunningTimers
