---
name: omp-built-in-npc-scripting
description: Use when open.mp needs server-side bots, not FCNPC.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, npc, bots]
    category: samp
---

# Built-in NPCs: create, spawn, and account for the player slot

open.mp v1.5.8.3079 made NPCs a server component. `NPC_Create` returns an
`INVALID_NPC_ID` on older servers, so the version gate comes first, then lifecycle.
FCNPC is the plugin for SA-MP and pre-1.5.8 open.mp; its functions are prefixed
`FCNPC_` and none of them exist in the built-in API.

## When to Use

- You need shopkeepers, guards or ambient bots and do not want the FCNPC plugin.
- You are porting `FCNPC_Create`/`FCNPC_Spawn` calls and the include no longer compiles.
- Bots appear as duplicate names, never move, or the server refuses new players at
  `max_players`.
- Not for scripted taxi routes recorded from a `.rec` file — that is record playback
  (`NPC_LoadRecord`, `NPC_StartPlayback`), a different lifecycle.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 (2026 baseline) | NPC API present |
| open.mp server | 1.5.8.3079 | first release with `NPC_*`; earlier builds fail at compile |
| open.mp server | 1.4.0.2779 and older | no `NPC_Create`; use FCNPC or upgrade |
| Legacy path | FCNPC plugin (`FCNPC_*`) | still valid for SA-MP 0.3.7-R2 |
| Slot model | `MAX_PLAYERS` | every NPC holds a player slot; the player count includes them |
| Declarations | `NPC_*` natives from the open.mp Pawn includes | confirm with the grep in Verification |
| Name rule | `NPC_Create(name[])` | max 24 characters, same charset as `SetPlayerName` |

## Production Implementation

1. Confirm the server build actually exposes the natives before writing code:

```bash
grep -rn "native NPC_Create" includes/ | head -3
```

2. Create every bot once in `OnGameModeInit`, keep the ids in a fixed array, and
   count them — a half-created bot left at `INVALID_NPC_ID` is what crashes later
   loops:

```pawn
#define MAX_BOTS (8)

new g_Bot[MAX_BOTS];
new g_BotCount;

public OnGameModeInit()
{
    for (new i = 0; i < MAX_BOTS; i++)
    {
        new name[24];
        format(name, sizeof name, "ShopBot_%d", i);
        g_Bot[i] = NPC_Create(name);
        if (!NPC_IsValid(g_Bot[i]))
        {
            g_Bot[i] = INVALID_NPC_ID;
            printf("[NPC] create failed for %s", name);
            continue;
        }
        g_BotCount++;
    }
    printf("[NPC] %d/%d bots created", g_BotCount, MAX_BOTS);
    return 1;
}
```

3. `NPC_Create` does not spawn anything. Do skin, position, interior and world in
   `OnNPCSpawn`, which fires when `NPC_Spawn` succeeded:

```pawn
public OnNPCSpawn(npcid)
{
    NPC_SetSkin(npcid, 230);
    NPC_SetPos(npcid, 1481.0, -1770.0, 18.8);
    NPC_SetInterior(npcid, 0);
    NPC_SetVirtualWorld(npcid, 0);
    printf("[NPC] %d spawned at the shop", npcid);
    return 1;
}
```

4. Free the ids on shutdown. Without this a `gmx` leaves ghost bots holding slots and
   the next init fails every create:

```pawn
public OnGameModeExit()
{
    for (new i = 0; i < MAX_BOTS; i++)
    {
        if (NPC_IsValid(g_Bot[i]))
        {
            NPC_Destroy(g_Bot[i]);
        }
        g_Bot[i] = INVALID_NPC_ID;
    }
    return 1;
}
```

5. Budget the slots. Bots consume player slots, so a 50-slot box running 8 bots accepts
   42 humans:

```bash
grep -n '"max_players"' config.json
```

Set `max_players` above `humans + MAX_BOTS`, and leave `network.grace_period`
(default 5000 ms) alone — it allows the burst of connections bots make at startup
from one IP.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Compile error: `NPC_Create` undefined | server/includes older than 1.5.8.3079 | upgrade server and includes, or keep FCNPC |
| `NPC_IsValid` true but no bot in game | `NPC_Spawn` never called | spawn, then set skin/pos in `OnNPCSpawn` |
| Bots pile up after `gmx`, creates start failing | ids never destroyed | `NPC_Destroy` loop in `OnGameModeExit` |
| Players rejected at `max_players` once bots start | NPCs hold player slots | raise `max_players` by `MAX_BOTS` |
| Bot has a truncated or rejected name | `NPC_Create` caps at 24 chars | shorten the `format` pattern |
| Bot spawns at 0,0,0 or the wrong interior | position set before spawn completes | set position in `OnNPCSpawn` |
| `FCNPC_*` calls left in the code | half-finished port | map to `NPC_*`; keep FCNPC only for 0.3.7 |

## Verification

Compile the gamemode with the same includes the server loads — natives that do not
exist fail here, not at runtime:

```bash
pawncc -d3 -iincludes gamemodes/your_mode.pwn
```

Expected: exit status `0` and no `undefined symbol` lines.

Then start the server and read the log the prints above write:

```bash
./omp-server > /tmp/omp.log 2>&1 &
sleep 5 && grep -E "\[NPC\]" /tmp/omp.log
```

Expected: one `[NPC] X/Y bots created` line plus one `spawned` line per bot, and no
`create failed` line. Cross-check in game by pressing TAB — the bots must show in the
player list under their bot names.

## Sources (2026)

- https://open.mp/docs/scripting/functions/NPC_Create
- https://open.mp/docs/scripting/callbacks/OnNPCSpawn
- https://open.mp/docs/changelog
