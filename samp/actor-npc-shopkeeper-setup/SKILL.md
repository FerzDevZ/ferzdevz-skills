---
name: actor-npc-shopkeeper-setup
description: Use when a shopkeeper actor or NPC misbehaves.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, actors, npc]
    category: samp
---

# Static actors for counters, NPCs only when you need behaviour

## When to Use

- A shopkeeper stands still, ignores the player, or slides away after a car hits it.
- The animation plays once and freezes, or the pay animation never starts.
- Somebody proposes one simulated player per shop and player slots are already tight.
- Not for anything that must walk, aim, drive or take damage; that is NPC work.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `CreateActor` family is core, no plugin |
| actor pool | `MAX_ACTORS` = 1000 | `CreateActor` returns `INVALID_ACTOR_ID` (65535) at the cap |
| NPC core | `NPC_Create`, omp 1.5.8.3079+ | an NPC consumes a player slot, an actor does not |
| animation | `ApplyActorAnimation`, delta 4.1 | library must be preloaded per player |
| interaction | `GetPlayerTargetActor` | aimed-at actor, not the nearest one |

## Production Implementation

1. Keep counters as data, one row each, and create them in one function:

```pawn
#include <open.mp>

#define MAX_SHOPS     (3)
#define SHOP_RANGE    (3.0)

enum E_SHOP { shopActor, shopSkin, shopWorld, Float:shopX, Float:shopY, Float:shopZ, Float:shopAngle };

static const gShopData[MAX_SHOPS][E_SHOP] =
{
    { -1, 205, 0, 1367.6, -1279.8, 13.5, 180.0 },   // 24/7 Idlewood
    { -1, 165, 0, 2127.2, -1135.9, 25.5,  90.0 },   // clothing store
    { -1, 230, 0,  681.4,  -472.4, 16.3,   0.0 }    // ammunation counter
};

new gShopActor[MAX_SHOPS];
new gPinTimer = -1;
new gClerkNpc = -1;

stock ShopSpawnAll()
{
    new created;
    for (new i = 0; i < MAX_SHOPS; i++)
    {
        gShopActor[i] = CreateActor(gShopData[i][shopSkin], gShopData[i][shopX],
            gShopData[i][shopY], gShopData[i][shopZ], gShopData[i][shopAngle]);

        if (gShopActor[i] == INVALID_ACTOR_ID)
        {
            printf("[shop] row=%d refused: actor pool exhausted", i);
            continue;
        }

        SetActorVirtualWorld(gShopActor[i], gShopData[i][shopWorld]);
        SetActorFacingAngle(gShopActor[i], gShopData[i][shopAngle]);
        ApplyActorAnimation(gShopActor[i], "DEALER", "shop_pay", 4.1, true, true, true, false, 0);
        created++;
    }
    printf("[shop] actors=%d/%d", created, MAX_SHOPS);
    return created;
}
```

2. Preload the library per player or the actor has nothing to play on that client: `ApplyAnimation(playerid, "DEALER", "null", 4.1, false, false, false, false, 0)` in `OnPlayerConnect`.

3. Re-pin on a slow timer against the table, not against the last read position, so repeated pushes cannot creep:

```pawn
forward ShopPin();
public ShopPin()
{
    for (new i = 0; i < MAX_SHOPS; i++)
    {
        if (gShopActor[i] == INVALID_ACTOR_ID) continue;
        new Float:x, Float:y, Float:z;
        GetActorPos(gShopActor[i], x, y, z);
        if (floatabs(x - gShopData[i][shopX]) > 1.0 || floatabs(y - gShopData[i][shopY]) > 1.0)
        {
            SetActorPos(gShopActor[i], gShopData[i][shopX], gShopData[i][shopY], gShopData[i][shopZ]);
            SetActorFacingAngle(gShopActor[i], gShopData[i][shopAngle]);
            printf("[shop] actor=%d pinned from %.1f %.1f", gShopActor[i], x, y);
        }
    }
    return 1;
}
```

4. Open the dialog from the aimed-at actor, then re-check distance server-side; the target is client-assisted and the range check is the real gate:

```pawn
stock ShopIndexByActor(actorid)
{
    for (new i = 0; i < MAX_SHOPS; i++) if (gShopActor[i] == actorid) return i;
    return -1;
}

public OnPlayerKeyStateChange(playerid, newkeys, oldkeys)
{
    if (!(newkeys & KEY_SECONDARY_ATTACK) || (oldkeys & KEY_SECONDARY_ATTACK)) return 1;
    new idx = ShopIndexByActor(GetPlayerTargetActor(playerid));
    if (idx == -1) return 1;
    new Float:sx, Float:sy, Float:sz;
    GetActorPos(gShopActor[idx], sx, sy, sz);
    if (GetPlayerDistanceFromPoint(playerid, sx, sy, sz) > SHOP_RANGE) return 1;
    ShowPlayerDialog(playerid, 900 + idx, DIALOG_STYLE_TABLIST, "Shop",
        "Bread\t$2\nWater\t$1\nBandage\t$5", "Buy", "Close");
    return 1;
}
```

5. Use an NPC only where a body must move; a created NPC is not in the world until `NPC_Spawn`. Tear both pools down on exit, or the 1000-slot pool leaks across restarts:

```pawn
stock ShopSpawnClerkNpc()
{
    gClerkNpc = NPC_Create("Shop_Clerk");
    if (!NPC_IsValid(gClerkNpc)) return 0;
    NPC_Spawn(gClerkNpc);
    NPC_SetPos(gClerkNpc, 1367.6, -1279.8, 13.5);
    printf("[shop] npc=%d valid=%d", gClerkNpc, NPC_IsValid(gClerkNpc));
    return 1;
}

stock ShopTeardown()
{
    if (gPinTimer != -1) { KillTimer(gPinTimer); gPinTimer = -1; }
    for (new i = 0; i < MAX_SHOPS; i++) if (IsValidActor(gShopActor[i])) DestroyActor(gShopActor[i]);
    if (NPC_IsValid(gClerkNpc)) NPC_Destroy(gClerkNpc);
    printf("[shop] torn down, pool=%d", GetActorPoolSize());
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| actor stands but never animates | library not preloaded for the client | `ApplyAnimation(playerid, "DEALER", "null", ...)` on connect |
| actor drifts off the counter | vehicle push persists | re-pin timer comparing against the table |
| `CreateActor` returns 65535 | pool exhausted by leftovers | destroy on exit, check `INVALID_ACTOR_ID` per row |
| counter invisible to some players | created in a world the player is not in | `SetActorVirtualWorld` from the same table |
| NPC never appears | created but never spawned | `NPC_Spawn`, verify with `NPC_IsValid` |
| shop opens from across the map | trusting `GetPlayerTargetActor` alone | distance check before `ShowPlayerDialog` |

## Verification

```bash
grep -c "CreateActor(" gamemodes/shops.pwn; grep -c "INVALID_ACTOR_ID\|DestroyActor\|NPC_IsValid" gamemodes/shops.pwn
```

Expected: `1` then a non-zero count — every actor comes from `ShopSpawnAll`, so a second call site is a review failure. Boot log must show `[shop] actors=3/3`, then `[shop] npc=0 valid=1` if enabled. After a gmx the previous run prints `[shop] torn down, pool=0` and the next boot still creates `3/3`; `0/3` means the pool leaked.

## Sources (2026)

- [open.mp — CreateActor](https://open.mp/docs/scripting/functions/CreateActor) — 1000 cap, `INVALID_ACTOR_ID`, invulnerable default, vehicles push actors.
- [open.mp — ApplyActorAnimation](https://open.mp/docs/scripting/functions/ApplyActorAnimation) — parameter order, delta 4.1, `DEALER`/`shop_pay` example with preload.
- [open.mp — NPC_Create](https://open.mp/docs/scripting/functions/NPC_Create) — omp 1.5.8.3079, requires `NPC_Spawn`.
