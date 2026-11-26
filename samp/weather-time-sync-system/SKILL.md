---
name: weather-time-sync-system
description: Use when weather or clock drifts per player world.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, world, weather, time, sync]
    category: samp
---

# One environment table, applied per player world

`SetWeather` and `SetWorldTime` are server-wide: they change the environment for everyone in
every world. Once the map has more than one virtual world — an interior district, a race
instance, an event world — the global call fights itself and players report rain in a desert
or a clock that jumps on respawn. The fix is a table keyed by world, applied with the
per-player natives and only when a value actually changed.

## When to Use

- Different virtual worlds need different weather, or one world resets on respawn.
- The in-game clock jumps back after a restart, or runs at the wrong speed.
- `SetWeather` is called from a timer and every player's screen flickers.
- An interior or event world keeps inheriting the main world's weather.

## Compatibility & Stack Matrix (2026)

| Item | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | identical behaviour on 0.3.7-R2 |
| Global weather | `SetWeather(id)` | every player in every world |
| Global clock | `SetWorldTime(hour)` | hour only, no minutes, all worlds |
| Per-player weather | `SetPlayerWeather(playerid, id)` | lost on reconnect, re-apply on spawn |
| Per-player clock | `SetPlayerTime(playerid, hour, minute)` | minutes supported, per client |
| Read back | `GetPlayerWeather` / `GetPlayerTime` | the only trustworthy verification |
| World source | `GetPlayerVirtualWorld(playerid)` | interiors inherit their world's env |
| Weather ids | 0..20 in the shipped set | ids outside it fall back to a default look |
| Persistence | your own file or DB row | env is not remembered across restarts |

Per-player values do not survive a reconnect, and the first per-player call overrides the global call.

## Production Implementation

1. Keep the environment in one table indexed by world, with an explicit default — not world
   0's weather leaking into a world nobody configured:

```pawn
#include <openmp>
#include <sscanf2>

#define MAX_ENV_WORLDS (32)

enum E_Env { envWeather, envHour, envMinute }

new gEnv[MAX_ENV_WORLDS][E_Env];
new gAppliedMinute[MAX_PLAYERS];
new gAppliedWeather[MAX_PLAYERS];

stock EnvInit()
{
    for (new w = 0; w < MAX_ENV_WORLDS; w++)
    {
        gEnv[w][envWeather] = 1;    // sunny
        gEnv[w][envHour]    = 12;
        gEnv[w][envMinute]  = 0;
    }
    gEnv[7][envWeather] = 8;        // storm world 7
}
```

2. Apply with the per-player natives and remember what you applied. Without that memory the
   timer re-sends identical weather every minute, which is a client re-render each time:

```pawn
stock EnvApply(playerid, world = -1)
{
    if (world < 0) world = GetPlayerVirtualWorld(playerid);
    if (world < 0 || world >= MAX_ENV_WORLDS) world = 0;

    SetPlayerWeather(playerid, gEnv[world][envWeather]);
    SetPlayerTime(playerid, gEnv[world][envHour], gEnv[world][envMinute]);

    gAppliedWeather[playerid] = gEnv[world][envWeather];
    gAppliedMinute[playerid]  = gEnv[world][envMinute];
}

public OnPlayerConnect(playerid) { gAppliedMinute[playerid] = -1; return 1; }
public OnPlayerSpawn(playerid)   { EnvApply(playerid); return 1; }
```

3. Advance the clock on one timer and push only the deltas. One game minute per real minute
   matches the engine's rate; the global call stays as a baseline for world 0 only:

```pawn
forward EnvTick();
public EnvTick()
{
    for (new w = 0; w < MAX_ENV_WORLDS; w++)
    {
        if (++gEnv[w][envMinute] < 60) continue;
        gEnv[w][envMinute] = 0;
        gEnv[w][envHour] = (gEnv[w][envHour] + 1) % 24;
    }

    SetWorldTime(gEnv[0][envHour]);          // baseline for players with a passing clock

    for (new playerid = 0; playerid < MAX_PLAYERS; playerid++)
    {
        if (!IsPlayerConnected(playerid)) continue;
        new w = GetPlayerVirtualWorld(playerid);
        if (w < 0 || w >= MAX_ENV_WORLDS) w = 0;
        if (gAppliedMinute[playerid]  == gEnv[w][envMinute] &&
            gAppliedWeather[playerid] == gEnv[w][envWeather]) continue;
        EnvApply(playerid, w);
    }
}
// boot: EnvInit(); read the table from world.env; SetTimer("EnvTick", 60000, true);
```

4. Persist the table, not the players: one line per world, `weather_<world>=<id>,<hour>,<minute>`,
   loaded at boot before anyone connects and re-written when an admin changes a world. Read it
   with `fread` plus `sscanf` and drop out-of-range rows instead of trusting the file — a bad
   weather id is a silent client fallback that looks like a script bug.

5. Change weather through one path — assign `gEnv[world][envWeather]`, then loop the players
   in that world and call `EnvApply` — so the tick and the clients agree at once instead of up
   to a minute later. Interiors need no special handling: `SetPlayerTime` covers them, because
   lighting is the world's business and not the weather's.

6. Never call `SetWeather` per tick. It re-broadcasts to every client; on a busy server the cost
   shows up as frame-time spikes in the same second every time, not as a crash.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Weather changes for everyone when one world is edited | `SetWeather` used per world | `SetPlayerWeather` for that world's players |
| Clock jumps back after respawn | per-player time lost on reconnect | `EnvApply` in `OnPlayerSpawn` |
| Screen flickers every minute | full re-apply on the timer | compare `gAppliedMinute` and `gAppliedWeather` |
| World 7 shows world 0's weather | default table never overridden | explicit default plus per-world overrides |
| Weather resets after a restart | env never persisted | load the table at boot, save on change |
| Interior stays bright at midnight | only global time set | `SetPlayerTime` per player, indoors included |
| Time drifts per hour | per-tick accumulation | one 60 s timer, or recompute from a wall clock |

## Verification

The persisted table is checked before boot: every world line needs a weather id in the shipped
0..20 set and an hour in 0..23.

```bash
awk -F'[=,]' '/^weather_/ { if ($2 < 0 || $2 > 20) { print "bad weather", $1, $2; bad++ }
                             if ($3 < 0 || $3 > 23) { print "bad hour", $1, $3; bad++ } n++ }
              END { print (bad ? "FAIL" : "env ok"), n, "rows" }' world.env
```

Expected on a healthy table:

```text
env ok 32 rows
```

Then read live values back: an `/env` command printing `GetPlayerWeather` and `GetPlayerTime` must
match the table for that player's world, with two players in two worlds at once.

## Sources (2026)

- https://open.mp/docs/scripting/functions/SetPlayerWeather — per-player weather, independent of the global call.
- https://open.mp/docs/scripting/functions/SetPlayerTime — per-player hour and minute; `SetWorldTime` takes only an hour.
- https://open.mp/docs/scripting/functions/SetWorldTime — global clock, relevant only to clients using a passing clock.
