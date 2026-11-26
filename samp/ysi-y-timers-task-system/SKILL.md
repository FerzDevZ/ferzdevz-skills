---
name: ysi-y-timers-task-system
description: Use when raw SetTimerEx ids leak or fight per player.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi, timers]
    category: samp
---

# Repeating work with YSI y_timers

## When to Use
- Timer ids are stored in globals, overwritten, and a `KillTimer` fires on the wrong feature.
- You want per-player repeating work that stops by itself when the player leaves.
- A `SetTimerEx` call and its callback have drifted apart: the interval lives in one place and the argument format in another.

## Compatibility & Stack Matrix (2026)
| Component | Version | Notes |
| --- | --- | --- |
| YSI | 5.x (`YSI_Coding/y_timers.inc`) | `task`, `ptask`, `timer`, `defer`, `repeat`, `stop` are macros over managed timers |
| open.mp | 1.x | identical behaviour; timers die with the AMX |
| SA-MP | 0.3.7-R5 | identical behaviour |
| pawncc | 3.10.10+ | `-;+ -(+ -d3`; a task's parameter list is checked at compile time |
| Include path | `-i./includes` | `<YSI_Coding\y_timers>` must resolve before any timer compiles |

YSI must be installed: verify `includes/YSI_Coding/y_timers.inc` exists and that a one-line file including it compiles. Include the public header only — it pulls in `y_timers/y_timers_entry` itself, so never include the internal files directly.

## Production Implementation
1. Pick the primitive by lifetime: `task` = forever, one instance; `ptask` = forever, per connected player; `timer` = on demand, startable and stoppable.
2. Give every timer a single interval in the definition and never pass a delay at the call site unless you deliberately override with `[ms]`.
3. Pass data as timer parameters, not through globals — the values are captured at call time.
4. Re-arm a one-shot `timer` with `defer Name[ms](args)` instead of a global id you have to track.
5. Check `IsPlayerConnected` as the first line of any per-player body; slots are recycled.
6. Keep intervals at 200 ms or longer unless the work is a rendered countdown.

```pawn
#include <YSI_Coding\y_timers>

new gHunger[MAX_PLAYERS];

task WeatherTick[600000]()                 // global, one instance, forever
{
    SetWeather(random(20));                // 0..19 are the valid weather ids
    return 1;
}

ptask VitalsTick[1000](playerid)           // per player, once a second, forever
{
    if (!IsPlayerConnected(playerid)) return 1;
    if (--gHunger[playerid] < 0) gHunger[playerid] = 0;
    return 1;
}
```

`task` takes no parameters beyond nothing at all; the per-player repeating form is `ptask`. A one-shot countdown is a `timer` that re-arms itself:

```pawn
timer JailTick[1000](playerid, seconds_left)
{
    if (!IsPlayerConnected(playerid)) return 1;      // player gone: the chain ends here

    if (--seconds_left <= 0)
    {
        SetPlayerInterior(playerid, 0);
        SetPlayerPos(playerid, 1544.0, -1675.0, 13.5);
        return 1;                                    // no re-arm: this timer is done
    }

    SendClientMessage(playerid, 0xFFFFFFAA, "Jail: %d s", seconds_left);
    defer JailTick[1000](playerid, seconds_left);    // re-arm with the captured value
    return 1;
}

stock StartJail(playerid, seconds)
{
    defer JailTick(playerid, seconds);               // uses the declared 1000 ms
    return 1;
}
```

Use `repeat` only when something else must be able to stop it, and keep the `Timer:` handle at the same scope as the `stop`:

```pawn
new Timer:gPayday[MAX_PLAYERS];

stock StartPayday(playerid)
{
    gPayday[playerid] = repeat PaydayMessage(playerid);
    return 1;
}

timer PaydayMessage[60000](playerid)
{
    SendClientMessage(playerid, 0x66FF66AA, "Payday in 60 seconds.");
    return 1;
}

stock StopPayday(playerid)
{
    stop gPayday[playerid];
    return 1;
}
```

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| `error 025: function heading differs` | a `task` was given a parameter list | `task` takes none; use `ptask` or `timer` |
| timer fires for the wrong player | id stored per slot, slot reused after reconnect | `IsPlayerConnected` first line, or pass values as parameters |
| server load climbs with player count | a global `task` loops all players every tick | convert to `ptask` so YSI balances per player |
| two equal-period tasks run together | balancing is only within the same period | offset one by a few hundred ms or merge them |
| `stop` appears to do nothing | a `task` has no handle | tasks are permanent; use `timer` + `repeat` |
| interval ten times too fast | milliseconds, not seconds | `[1000]` is one second, `[1000 * 60]` one minute |
| work queues up under load | interval shorter than the body | measure the body, raise the interval, split the work |

## Verification
```bash
grep -rn "SetTimerEx\?(" gamemodes/modules | wc -l
```
Expected: `0` for a migrated subsystem — no raw timer calls left behind.

```bash
grep -rn "^task \|^ptask \|^timer " gamemodes/modules | wc -l
```
Expected: the number of timer definitions you intended, one line each, with no duplicate names.

Runtime: tail the log for a per-second task and compare timestamps; they must be ~1 s apart and must stop within one interval of the last player disconnecting:

```bash
grep VitalsTick logs/server.log | tail -3 | awk '{print $1, $2}'
```
Expected: three consecutive timestamps one second apart, and no further lines after the disconnect marker.

## Sources (2026)
- [y_timers quick start](https://raw.githubusercontent.com/pawn-lang/YSI-Includes/5.x/YSI_Coding/y_timers/quick-start.md) — `task`/`ptask`/`timer` forms, `defer`, `repeat`, `stop`, interval override and balancing.
- [YSI-Includes 5.x](https://github.com/pawn-lang/YSI-Includes) — `YSI_Coding/y_timers` include path and library grouping.
- [open.mp documentation](https://open.mp/docs) — 2026 server lifecycle; timers do not survive an AMX unload.
