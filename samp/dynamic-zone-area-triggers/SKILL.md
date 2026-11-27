---
name: dynamic-zone-area-triggers
description: Use when streamer area callbacks fire twice or never.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer, zones]
    category: samp
---

# Trigger gameplay on dynamic areas without double fires

Streamer areas are edge events from the plugin's own tick, not the server frame. A 2D area has no
height, and the callback can repeat for an area the player already stands in — your state is the truth.

## When to Use

- A zone fires on every tick inside the area, or twice for one crossing.
- A zone never fires although the coordinates match the map.
- Players in another world or interior trigger a shop zone that belongs to world 0.
- State stays "inside" after death, teleport, or a gamemode reload.

## Compatibility & Stack Matrix (2026)

| Item | 2026 baseline | Behaviour that bites |
| --- | --- | --- |
| Plugin | streamer 2.9.6 (legacy plugin) | include `streamer.inc` from the same release, not `omp-stdlib` |
| 2D shapes | `CreateDynamicCircle(x, y, size, worldid, interiorid, playerid)` | no z: infinite height, so a roof counts as inside |
| 3D shapes | `CreateDynamicCylinder(x, y, minz, maxz, size, ...)` | `minz`/`maxz` are absolute world Z, not offsets |
| World / interior | `-1` means any, an explicit id means exact match | passing `0` silently makes the zone world-0 only |
| Callbacks | `OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid)` and `...Leave...` | fired from the streamer tick (50 ms default), re-emitted after updates |
| Spectate | areas trigger in spectate mode by default | `ToggleDynAreaSpectateMode(areaid, false)` |

## Production Implementation

1. Declare zones as data, create each once, and keep the plugin's tagged handle instead of a plain
   integer:

```pawn
#define MAX_ZONES 8

enum E_ZONE
{
    ZONE_NAME[24], Float:ZONE_X, Float:ZONE_Y, Float:ZONE_MINZ,
    Float:ZONE_MAXZ, Float:ZONE_R, ZONE_WORLD, ZONE_INTERIOR
}

new const g_ZoneData[][E_ZONE] =
{
    {"Shop LS", 1368.0, -1279.0,  8.0, 24.0, 12.0, 0, 0},
    {"Arena",  -1958.0,   298.0,  0.0, 40.0, 60.0, 7, 0}
};

new STREAMER_TAG_AREA:g_ZoneArea[MAX_ZONES];
new bool:g_InZone[MAX_PLAYERS][MAX_ZONES];

stock Zones_Init()
{
    for (new i = 0; i < MAX_ZONES; i++)
    {
        g_ZoneArea[i] = CreateDynamicCylinder(g_ZoneData[i][ZONE_X], g_ZoneData[i][ZONE_Y],
                                             g_ZoneData[i][ZONE_MINZ], g_ZoneData[i][ZONE_MAXZ],
                                             g_ZoneData[i][ZONE_R],
                                             g_ZoneData[i][ZONE_WORLD], g_ZoneData[i][ZONE_INTERIOR]);
        if (!IsValidDynamicArea(g_ZoneArea[i])) printf("ZONE_INIT failed index=%d", i);
    }
    printf("ZONE_INIT created=%d counted=%d", MAX_ZONES, CountDynamicAreas());
    return 1;
}
```

2. Look the area id up instead of casting it to an index — ids come from the plugin and are not
   dense — then guard both edges with your own state. Resync after anything that moves a player
   without a crossing, because the plugin is up to one tick behind a teleport:

```pawn
stock Zone_Index(STREAMER_TAG_AREA:areaid)
{
    for (new i = 0; i < MAX_ZONES; i++) if (g_ZoneArea[i] == areaid) return i;
    return -1;
}

public OnPlayerEnterDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
    new z = Zone_Index(areaid);
    if (z == -1 || g_InZone[playerid][z]) return 1;    // re-emitted, not a new crossing
    g_InZone[playerid][z] = true;
    Zone_Apply(playerid, z, true);
    return 1;
}

public OnPlayerLeaveDynamicArea(playerid, STREAMER_TAG_AREA:areaid)
{
    new z = Zone_Index(areaid);
    if (z == -1 || !g_InZone[playerid][z]) return 1;
    g_InZone[playerid][z] = false;
    Zone_Apply(playerid, z, false);
    return 1;
}

stock Zone_Resync(playerid)
{
    for (new i = 0; i < MAX_ZONES; i++)
    {
        new bool:inside = bool:IsPlayerInDynamicArea(playerid, g_ZoneArea[i]);
        if (inside == g_InZone[playerid][i]) continue;
        g_InZone[playerid][i] = inside;
        Zone_Apply(playerid, i, inside);
    }
    return 1;
}
```

3. Resolve overlapping areas in one function, ordered by priority. Two callbacks that each pay out is
   how a player collects two wages for one shop:

```pawn
stock Zone_Apply(playerid, zone, bool:entered)
{
    printf("ZONE_%s p=%d zone=%d area=%d world=%d int=%d", entered ? "ENTER" : "LEAVE", playerid, zone,
           _:g_ZoneArea[zone], GetPlayerVirtualWorld(playerid), GetPlayerInterior(playerid));
    if (entered) Shop_OnEnter(playerid);
    else Shop_OnLeave(playerid);
    return 1;
}
```

4. Reset flags on disconnect and destroy on exit, so a reload leaves no second copy of a zone:

```pawn
public OnPlayerDisconnect(playerid, reason)
{
    for (new i = 0; i < MAX_ZONES; i++) g_InZone[playerid][i] = false;
    return 1;
}
public OnGameModeExit()
{
    for (new i = 0; i < MAX_ZONES; i++)
        if (IsValidDynamicArea(g_ZoneArea[i])) DestroyDynamicArea(g_ZoneArea[i]);
    return 1;
}
```
## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Fires every tick while standing still | polling `IsPlayerInDynamicArea` in `OnPlayerUpdate` as the trigger | edge events only, plus `Zone_Resync` after teleports |
| Two payouts for one crossing | no previous-state guard, callback re-emitted | `g_InZone` check in both callbacks |
| Never fires, coordinates are correct | zone created with world `0` instead of `-1` | explicit world id per zone, log `GetPlayerVirtualWorld` |
| Roof above the shop triggers the shop | 2D `CreateDynamicCircle` has no height | `CreateDynamicCylinder` with real `minz`/`maxz` |
| State stuck after death or teleport | exit never observed while the player moved | `Zone_Resync` on spawn and after any `SetPlayerPos` |
| Zones double after `/gmx` | areas recreated, old ones never destroyed | destroy in `OnGameModeExit`, compare `CountDynamicAreas()` |

## Verification

```bash
pawncc gamemodes/zones.pwn -i"$HOME/samp-sdk/omp-stdlib" -i"$HOME/samp-sdk/includes" -o/tmp/zones.amx -d3
grep -c 'ZONE_ENTER' /opt/omp-server/log.txt
```

Expected: `Done.` with no warnings (`streamer.inc` from the 2.9.6 release in the second include
directory), one `ZONE_INIT created=2 counted=2` at boot, and one `ZONE_ENTER` per crossing: walk in
and out three times, the count is 3, not 30. After `/gmx` the next boot must still read `counted=2`.

## Sources (2026)

- https://github.com/samp-incognito/samp-streamer-plugin/wiki/Natives-(Areas)
- https://github.com/samp-incognito/samp-streamer-plugin
- https://github.com/samp-incognito/samp-streamer-plugin/blob/master/streamer.inc
