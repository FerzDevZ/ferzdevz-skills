---
name: omp-npc-pathfinding-combat
description: Use when open.mp bots must patrol, aim and shoot.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, npc, pathfinding, combat]
    category: samp
---

# Paths and combat: give the bot a route, then a weapon

Paths are a separate pool from NPCs: `NPC_CreatePath` builds a route once and any number
of NPCs walks it with `NPC_MoveByPath`. Aiming is server-side too — `NPC_AimAtPlayer`
takes the shot delay and offsets, so a bot that "aims wrong" is a parameter bug.

## When to Use

- Guards must patrol waypoints and open fire on players inside a radius.
- Bots teleport, jitter, or stop after the first waypoint.
- Ammo never decreases, or the bot fires after the target disconnected.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 baseline, path API since 1.5.8.3079 | all `NPC_*` calls below are built-in |
| Path pool | `NPC_CreatePath` → `NPC_DestroyPath` | ids leak if never destroyed |
| Move types | `NPC_MOVE_TYPE_WALK`, `NPC_MOVE_TYPE_JOG` (default), run | second argument of `NPC_MoveByPath` |
| Precision knob | `stopRange` in `NPC_AddPointToPath(path, x, y, z, stopRange)` | smaller = tighter cornering, more re-issues |
| Progress signal | `NPC_GetCurrentPathPointIndex` | poll on a 1 s timer, not per tick |

## Production Implementation

1. Build the route once at init. Every point needs its own `stopRange`; 1.5 m is a
   sane default for a sidewalk patrol, 0.8 m for interiors:

```pawn
new g_PatrolPath;

public OnGameModeInit()
{
    g_PatrolPath = NPC_CreatePath();
    if (!NPC_IsValidPath(g_PatrolPath))
    {
        printf("[NPC] path creation failed");
        return 1;
    }

    NPC_AddPointToPath(g_PatrolPath, 1481.0, -1770.0, 18.8, 1.5);
    NPC_AddPointToPath(g_PatrolPath, 1490.5, -1770.0, 18.8, 1.5);
    NPC_AddPointToPath(g_PatrolPath, 1490.5, -1755.0, 18.8, 1.5);
    NPC_AddPointToPath(g_PatrolPath, 1481.0, -1755.0, 18.8, 1.5);

    printf("[NPC] patrol path %d has %d points", g_PatrolPath,
           NPC_GetPathPointCount(g_PatrolPath));
    return 1;
}
```

2. Arm the bot on spawn, then start the walk. Reloading must be enabled explicitly,
   otherwise the bot fires the clip empty and stands there:

```pawn
public OnNPCSpawn(npcid)
{
    NPC_SetWeapon(npcid, WEAPON_DEAGLE);
    NPC_SetAmmo(npcid, 60);
    NPC_EnableReloading(npcid, true);
    NPC_EnableInfiniteAmmo(npcid, false);
    NPC_MoveByPath(npcid, g_PatrolPath, NPC_MOVE_TYPE_WALK);
    return 1;
}
```

3. Watch progress on one timer for all bots, and ping-pong the route when the index
   stops advancing. `reversed = true` walks the same points backwards, so the guard
   never needs a second path:

```pawn
forward GuardTick();
public GuardTick()
{
    for (new i = 0; i < MAX_BOTS; i++)
    {
        new npcid = g_Bot[i];
        if (!NPC_IsSpawned(npcid)) continue;

        new idx = NPC_GetCurrentPathPointIndex(npcid);
        if (idx != g_LastIdx[i])
        {
            g_LastIdx[i] = idx;
            if (idx >= NPC_GetPathPointCount(g_PatrolPath) - 1)
            {
                g_Reversed[i] = !g_Reversed[i];
                NPC_MoveByPath(npcid, g_PatrolPath, NPC_MOVE_TYPE_WALK, g_Reversed[i]);
            }
        }
    }
    return 1;
}
```

4. Combat is a state transition: aim once when a target enters range, stop when it
   leaves or disconnects:

```pawn
stock BotEngage(npcid, playerid)
{
    if (!IsPlayerConnected(playerid)) return 0;          // never aim at a stale id
    if (GetPlayerState(playerid) == PLAYER_STATE_WASTED) return 0;
    NPC_StopMove(npcid);
    NPC_AimAtPlayer(npcid, playerid, true, 900, true,
                    0.0, 0.0, 0.8,   // aim at chest height
                    0.0, 0.0, 0.0,   // fire from the NPC origin
                    0);
    return 1;
}

stock BotDisengage(npcid)
{
    NPC_StopAim(npcid);
    NPC_MoveByPath(npcid, g_PatrolPath, NPC_MOVE_TYPE_WALK);
    return 1;
}
```

5. Destroy the path in the shutdown block that destroys the bots:
   `if (NPC_IsValidPath(g_PatrolPath)) NPC_DestroyPath(g_PatrolPath);` — a leftover id is a
   slow leak across `gmx`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Bot stands still after `NPC_MoveByPath` | path empty or `NPC_IsValidPath` false | add points first, check the return value |
| Bot teleports between waypoints | `stopRange` far larger than the gap | drop to 0.8–1.5 m |
| Bot fires once then idles | `NPC_EnableReloading(npcid, false)` | enable reloading, keep ammo above clip size |
| Ammo never drops | infinite ammo enabled | `NPC_EnableInfiniteAmmo(npcid, false)` |
| Bot keeps shooting a player who left | aim started before `IsPlayerConnected` | gate every engage on connection state |
| Server tick drops as bot count rises | aiming/moving re-issued per tick | one timer at 1 s for all bots |
| Patrol stops at the last waypoint | index saturates and never restarts | re-issue `NPC_MoveByPath` with `reversed` |

## Verification

Compile first — path natives that the server lacks fail at compile time:

```bash
pawncc -d3 -iincludes gamemodes/your_mode.pwn
```

Expected: exit status `0`, no `undefined symbol`.

Then confirm the route exists with the right point count and that the bot advances:

```bash
./omp-server > /tmp/omp.log 2>&1 &
sleep 8 && grep -E "patrol path|path point" /tmp/omp.log
```

Expected: `[NPC] patrol path 0 has 4 points` and a rising `path point` line per bot
per waypoint. In game, the guard must walk the corners without sliding, and its ammo
count must fall while it is engaging a player.

## Sources (2026)

- https://open.mp/docs/scripting/functions/NPC_MoveByPath
- https://open.mp/docs/scripting/functions/NPC_AddPointToPath
- https://open.mp/docs/scripting/functions/NPC_AimAtPlayer
