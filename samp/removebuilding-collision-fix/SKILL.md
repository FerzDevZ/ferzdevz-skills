---
name: removebuilding-collision-fix
description: Use when players fall through holes in a removed building.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, collision]
    category: samp
---

# Remove buildings once per player, then patch the hole

## When to Use

- Players drop through the ground where a stock building was removed.
- Some players still see the building others removed, or a removal works only after a relog.
- A reconnect crashes the client right after the log line for building removal.
- Not for deleting an object you created yourself; `DestroyDynamicObject` is the call for that.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `RemoveBuildingForPlayer` is a core native |
| SA-MP 0.3.7 | R2 and later | same native, same per-player behaviour |
| removal budget | around 1000 per player | documented as a hard limit with "no workaround" |
| scope | per player, client side | the server has no global removal |
| counter | `GetPlayerBuildingsRemoved(playerid)` | returns how many the player's client accepted |
| collision | removed with the model | no native restores it; you add a replacement object |

Two consequences follow from the table: every player needs the same list, and anything that was walkable has to be rebuilt with a streamer object, because the removal takes the collision with it.

## Production Implementation

1. Generate the rows from the map diff, never by hand, and deduplicate while formatting. Identical rows are the usual cause of the reconnect crash, since a duplicated removal targets a model the client already deleted.

```bash
awk -F, 'NF >= 5 {printf "    { %s, %s, %s, %s, %s },\n", $1, $2, $3, $4, $5}' removals.raw \
  | sort -u > maps/removals.inc
grep -c '^    { ' maps/removals.inc
```

2. Keep the list in a generated file so the count is visible in review:

```pawn
#define MAX_REMOVALS (900)

enum E_Removal
{
    rmModel,
    Float:rmX,
    Float:rmY,
    Float:rmZ,
    Float:rmRadius
};

#include "maps/removals.inc"   // new const gRemovals[][E_Removal] = { ... }; one deduplicated row each
```

3. Send the list exactly once per connection. The guard is the fix for the documented crash: sending the same removal twice for the same player kills the client, and `OnPlayerSpawn` runs again on every death.

```pawn
new bool:gRemovalSent[MAX_PLAYERS];

stock SendRemovals(playerid)
{
    if (gRemovalSent[playerid])
        return 0;                        // second pass over the same list crashes the client

    gRemovalSent[playerid] = true;

    for (new i = 0; i < sizeof gRemovals; i++)
    {
        RemoveBuildingForPlayer(playerid, gRemovals[i][rmModel],
                                gRemovals[i][rmX],
                                gRemovals[i][rmY],
                                gRemovals[i][rmZ],
                                gRemovals[i][rmRadius]);
    }

    printf("[removals] player %d asked for %d, server reports %d",
           playerid, sizeof gRemovals, GetPlayerBuildingsRemoved(playerid));
    return 1;
}

public OnPlayerConnect(playerid)
{
    gRemovalSent[playerid] = false;      // the slot is reused after a reconnect
    SendRemovals(playerid);
    return 1;
}
```

4. Fail loudly at boot when the list outgrows the budget. Silent overflow looks like "the map half works", which costs hours to trace:

```pawn
public OnGameModeInit()
{
    new rows = sizeof gRemovals;

    if (rows > MAX_REMOVALS)
        printf("[removals] %d rows exceeds the ~1000 per-player budget; late rows are dropped", rows);
    return 1;
}
```

5. Rebuild what you deleted. Where the removed model was the floor, add a streamer object over the footprint with the same world and interior, and give it a solid material:

```pawn
enum E_Patch
{
    Float:ptX, Float:ptY, Float:ptZ, Float:ptW, Float:ptD
};

#include "maps/patches.inc"   // new const gFloorPatches[][E_Patch] = { { x, y, z, w, d }, ... };

stock AddFloorPatches()
{
    for (new i = 0; i < sizeof gFloorPatches; i++)
    {
        new obj = CreateDynamicObject(FLOOR_MODEL,
                                      gFloorPatches[i][ptX], gFloorPatches[i][ptY], gFloorPatches[i][ptZ],
                                      0.0, 0.0, 0.0, WORLD_LS, INTERIOR_NONE, -1, 400.0, 400.0);

        SetDynamicObjectMaterial(obj, 0, -1, "none", "none", 0xFF808080);
    }
    return 1;
}
```

`FLOOR_MODEL` is the flat model your map already uses; the vertex lighting loss from the colour-only material is covered in `dynamic-object-material-retexture`.

6. Remove the companions of the building, not only its main model. LOD copies and decorative pieces keep their own collision, so a hole can keep an invisible floor or a floating shadow.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| client crashes on reconnect, right after removal lines | the same removal sent again from `OnPlayerSpawn` | guard with a per-connection flag, send only from `OnPlayerConnect` |
| one building comes back after relog | list above the ~1000 row budget, later rows dropped | merge radii, split the map, keep the list under 900 |
| player falls through where the building stood | collision left with the removed model | add a floor patch object over the footprint |
| player sees the building, another does not | removal is per player and only one path calls it | call the same list for every connection |
| hole is there but a faint shadow or invisible wall remains | an LOD or duplicate model with its own collision | remove that model id too |
| building visible for a second after a teleport | list sent after the area already streamed | send at connect, before the first spawn |
| `GetPlayerBuildingsRemoved` stays at 0 | native called before the client finished connecting | read it after `SendRemovals`, not from `OnGameModeInit` |

## Verification

Count first: the generated list must be under the budget.

```bash
grep -c '^    { ' maps/removals.inc
```

Expected: a number at or below `900` (the native's own limit is around 1000). Then, in game, `/remcount` returns `GetPlayerBuildingsRemoved(playerid)` and must equal that number plus the patches you added, on a fresh connect and again after a relog without a crash. Compile gate:

```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```

Expected: `0 Errors` and `0 Warnings`.

## Sources (2026)

- [open.mp RemoveBuildingForPlayer](https://open.mp/docs/scripting/functions/RemoveBuildingForPlayer) — `-1` model id, ~1000 limit with "no workaround", duplicate-removal crash on reconnect.
- [open.mp GetPlayerBuildingsRemoved](https://open.mp/docs/scripting/functions/GetPlayerBuildingsRemoved) — per-player counter used for verification.
- [open.mp limits](https://open.mp/docs/scripting/resources/limits) — object and per-player pool limits the patches must stay inside.
