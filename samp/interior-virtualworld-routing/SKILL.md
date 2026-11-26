---
name: interior-virtualworld-routing
description: Use when interior teleports leak players or objects.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, world, interior]
    category: samp
---

# Route interiors through one table, worlds and streamer together

## When to Use

- A player lands in an interior but still sees the street, or the street sees them.
- Interior furniture shows up outside, or vanishes when the player walks back out.
- Players fall through the floor right after a door teleport.
- Two copies of the same house share furniture or share occupants.
- Not for plain spawn teleports in world 0; those need no routing table.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | same interior/world model as 0.3.7 |
| interiors | 0 to 255 in 0.3.7 (256 total) | above that the client does not switch |
| virtual worlds | up to 2,147,483,647 | default world is 0 |
| streamer | 2.9.6 | items filter on both `interiorid` and `worldid`; -1 matches all |
| `Streamer_UpdateEx` | 9 params | with `compensatedtime` -1 it never moves the player |
| order | interior and world first, position last | documented on the interior-id resource page |

The last two rows are the whole skill: the two ids are independent state, and the streamer needs a reason to re-evaluate them at the destination. `SetPlayerInterior` alone moves nobody and hides nothing.

## Production Implementation

1. Keep one table, loaded from a file, with both sides of every door. Interior ids are validated at load, not at teleport:

```pawn
#define MAX_ROUTES (64)
#define MAX_ROUTE_NAME (24)

enum E_Route
{
    rtName[MAX_ROUTE_NAME],
    Float:rtDoorX, Float:rtDoorY, Float:rtDoorZ, rtDoorWorld, rtDoorInterior,
    Float:rtInX, Float:rtInY, Float:rtInZ, rtInWorld, rtInInterior
};

new gRoutes[MAX_ROUTES][E_Route];
new gRouteCount;

stock RouteLoad()
{
    new File:f = fopen("routes.cfg", io_read);
    if (!f) { print("[routes] routes.cfg missing"); return 0; }

    new line[200];
    while (fread(f, line) && gRouteCount < MAX_ROUTES)
    {
        if (line[0] == '#' || line[0] == '\0') continue;

        if (sscanf(line, "s[24]fffddfffdd", gRoutes[gRouteCount][rtName],
                   gRoutes[gRouteCount][rtDoorX], gRoutes[gRouteCount][rtDoorY],
                   gRoutes[gRouteCount][rtDoorZ], gRoutes[gRouteCount][rtDoorWorld],
                   gRoutes[gRouteCount][rtDoorInterior], gRoutes[gRouteCount][rtInX],
                   gRoutes[gRouteCount][rtInY], gRoutes[gRouteCount][rtInZ],
                   gRoutes[gRouteCount][rtInWorld], gRoutes[gRouteCount][rtInInterior])
            || gRoutes[gRouteCount][rtInInterior] > 255)
            continue;                       // only 256 interiors exist; higher ids never switch

        gRouteCount++;
    }

    fclose(f);
    printf("[routes] %d loaded", gRouteCount);
    return 1;
}
```

2. One teleport function for every door. Interior and world first, vehicle linked before the player moves, then a single streamer call that moves and re-streams together:

```pawn
stock RouteTeleport(playerid, routeid, bool:enter)
{
    if (routeid < 0 || routeid >= gRouteCount) return 0;

    new Float:x, Float:y, Float:z, world, interior;

    if (enter)
    {
        x = gRoutes[routeid][rtInX];  y = gRoutes[routeid][rtInY];  z = gRoutes[routeid][rtInZ];
        world = gRoutes[routeid][rtInWorld];  interior = gRoutes[routeid][rtInInterior];
    }
    else
    {
        x = gRoutes[routeid][rtDoorX];  y = gRoutes[routeid][rtDoorY];  z = gRoutes[routeid][rtDoorZ];
        world = gRoutes[routeid][rtDoorWorld];  interior = gRoutes[routeid][rtDoorInterior];
    }

    new vehicleid = GetPlayerVehicleID(playerid);

    SetPlayerInterior(playerid, interior);
    SetPlayerVirtualWorld(playerid, world);

    if (vehicleid != 0)
    {
        LinkVehicleToInterior(vehicleid, interior);
        SetVehicleVirtualWorld(vehicleid, world);
    }

    // compensatedtime 0 also calls SetPlayerPos; freeze 1 is released on the next streamer tick
    Streamer_UpdateEx(playerid, x, y, z, world, interior, -1, 0, 1);
    return 1;
}
```

3. Pick the `Streamer_UpdateEx` mode on purpose: default `compensatedtime` (-1) re-streams around the given point and leaves the player where they stand, which is the preload call; a non-negative value performs the teleport, as `RouteTeleport` does.

4. Validate the door before moving anyone: distance plus the world the player must stand in, so a client cannot trigger a door from the other side of the map.

```pawn
CMD:enter(playerid, params[])
{
    for (new i = 0; i < gRouteCount; i++)
    {
        if (IsPlayerInRangeOfPoint(playerid, 2.0, gRoutes[i][rtDoorX], gRoutes[i][rtDoorY], gRoutes[i][rtDoorZ])
            && GetPlayerVirtualWorld(playerid) == gRoutes[i][rtDoorWorld])
            return RouteTeleport(playerid, i, true);
    }
    return SendClientMessage(playerid, 0xFF4444FF, "No door here.");
}
```

5. Create interior objects with both ids: `CreateDynamicObject(19483, x, y, z, 0.0, 0.0, 0.0, world, interior, -1, 150.0, 150.0)`. `-1` is a wildcard, not a default, and every wildcard object is drawn in every world.

6. Instance a house by deriving the world from its id and keeping one interior id: `world = HOUSE_WORLD_BASE + houseid`. Two houses then share furniture models but never share occupants, and a player re-entering the same house finds their state.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| player stands inside and still sees the street | interior changed, world left at 0 | set both ids in one place |
| furniture from one house appears in another | both houses created with the same `worldid` | derive the world from the house id |
| player falls through the floor after a door | position set before interior, or no streamer update at the destination | order interior/world, then `Streamer_UpdateEx` |
| player arrives frozen | freeze requested but the streamer never ticked (plugin missing or tick raised) | check the plugin load line and `Streamer_GetTickRate` |
| vehicle stays outside after entering | `LinkVehicleToInterior`/`SetVehicleVirtualWorld` not called | link the vehicle before moving the player |
| street objects visible from inside | objects created with `interiorid` -1 | pass the real interior id |

## Verification

```bash
awk '$11 > 255 || $6 > 255 {print "bad interior", $1}' routes.cfg; echo "routes ok"
```

Expected: no `bad interior` lines, then `routes ok`. In game, `/where` prints `GetPlayerInterior` and `GetPlayerVirtualWorld`; both must equal the row used and stay stable across a relog, and `Streamer_CountVisibleItems` must drop to the interior's own object count, not the street's. Compile gate:

```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```

Expected: `0 Errors` and `0 Warnings`.

## Sources (2026)

- [open.mp interior IDs](https://open.mp/docs/scripting/resources/interiorids) — `/interior` probe, set interior (and link vehicles) before `SetPlayerPos`.
- [open.mp SetPlayerVirtualWorld](https://open.mp/docs/scripting/functions/SetPlayerVirtualWorld) — default world 0, visibility scope.
- [open.mp limits](https://open.mp/docs/scripting/resources/limits) — 256 interiors, 2,147,483,647 virtual worlds.
