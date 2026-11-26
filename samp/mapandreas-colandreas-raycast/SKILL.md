---
name: mapandreas-colandreas-raycast
description: Use when ground height or a collision ray disagrees.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, world, raycast, plugins]
    category: samp
---

# MapAndreas answers "how high is the terrain"; ColAndreas answers "what did I hit"

The two plugins look interchangeable and are not. MapAndreas is a heightmap: it
knows the ground surface of the stock San Andreas terrain, ignores every object,
and has no idea what an interior is. ColAndreas builds a collision mesh from models
and answers a ray with a point. Choosing the wrong one produces the two classic
symptoms: an interior floor that "does not exist", and a custom object a player
walks straight through. Both sets of natives belong to their plugin includes, not
to the server.

## When to Use

- You need a ground Z for an anti-airbreak or fall-damage check outdoors.
- A raycast must hit a mapped object, a custom DFF or a vehicle.
- An interior floor returns street height, or `0`, from the heightmap.
- A custom object has no collision server-side while the client shows it.
- Not for streaming the objects themselves — that is `dynamic-object-map-loader`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| open.mp server | 1.6.x | plugins load via `pawn.legacy_plugins` or components |
| MapAndreas | 1.2.1 (Kalcor/Mauzen, philip1337 build) | natives in `mapandreas.inc`; heightmap in `scriptfiles` |
| MapAndreas modes | `MAP_ANDREAS_MODE_FULL` (3), `MINIMAL` (1), `NOBUFFER` (4) | mode sets memory and coverage |
| MapAndreas return | `MAP_ANDREAS_ERROR_SUCCESS` = 0 | any other value is an error code, not "success" |
| ColAndreas | Pottus build (Bullet-based) | natives in `colandreas.inc`; needs `scriptfiles/ColAndreas/ColAndreas.cadb` |
| ColAndreas init | `CA_Init()` after `CA_RemoveBuilding()` | removal before load, restore after load |
| Streamer | 2.9.6 | `CA_CreateDynamicObject_DC` wrapper ties collision to the object |
| Cost | MapAndreas one cell lookup; ColAndreas one ray through the mesh | never per player per tick |

## Production Implementation

1. Initialise both plugins at startup and check the return. `MapAndreas_Init`
   returns an error code from the include (0 is success), so a `if (!init)` test
   reads backwards and hides a missing `.hmap`.

```pawn
public OnGameModeInit()
{
    if (MapAndreas_Init(MAP_ANDREAS_MODE_FULL, "scriptfiles/SAFull.hmap") != MAP_ANDREAS_ERROR_SUCCESS)
    {
        print("[world] MapAndreas failed: check scriptfiles/SAFull.hmap");
    }
    return 1;
}
```

2. Order ColAndreas correctly: register building removals first, then build the
   mesh. Collisions for removed buildings that were added first stay in the mesh
   and produce invisible walls in mid-air.

```pawn
public OnGameModeInit()
{
    CA_RemoveBuilding(615, 0.0, 0.0, 0.0, 200.0);   // before the mesh loads
    CA_Init();                                       // loads the SA collision mesh
    return 1;
}
```

3. Use MapAndreas only where the stock terrain is the surface: outdoors, on foot or
   in a vehicle, `GetPlayerInterior(playerid) == 0`. It returns the terrain height,
   so for an interior it returns the street above or below the room.

```pawn
stock bool:TerrainZ(Float:x, Float:y, &Float:z)
{
    return bool:MapAndreas_FindZ_For2DCoord(x, y, z);   // 0 when outside the hmap
}

stock IsAirbreak(playerid, Float:tolerance)
{
    if (GetPlayerInterior(playerid) != 0) return 0;      // interiors: no terrain answer
    new Float:x, Float:y, Float:z, Float:ground;
    GetPlayerPos(playerid, x, y, z);
    if (!TerrainZ(x, y, ground)) return 0;               // no data, do not accuse
    return (z - ground) > tolerance;
}
```

4. Use ColAndreas for anything with models in it. A downward ray that starts above
   the player and ends below the floor returns 1 on a hit, 0 on nothing — the zeros
   are the informative case.

```pawn
stock Float:CollisionZ(Float:x, Float:y, Float:fromZ, &bool:hit)
{
    new Float:hx, Float:hy, Float:hz;
    hit = bool:CA_RayCastLine(x, y, fromZ, x, y, fromZ - 200.0, hx, hy, hz);
    return hz;
}
```

5. The include ships `stock CA_FindZ_For2DCoord(Float:x, Float:y, &Float:z)` — the
   MapAndreas call backed by a real collision ray, so it works on interiors and
   custom objects. Prefer it when the floor may be an object rather than terrain.

6. Register mapped and custom objects with ColAndreas, otherwise the server mesh
   and the client view disagree and players fall through a visible floor. The `_DC`
   wrapper creates the streamer object and the collision together:

```pawn
new obj = CA_CreateDynamicObject_DC(modelid, x, y, z, rx, ry, rz, world, interior);
if (!IsValidDynamicObject(obj)) printf("[world] collision wrapper failed for %d", modelid);
```

7. Cache by quantised cell and by tick. A ray per player per tick is the usual
   reason a 200-slot server idles at 40% CPU: sample on movement, and keep the
   result for a second or until the player moves more than a metre.

```pawn
new Float:g_LastX[MAX_PLAYERS], Float:g_LastZ[MAX_PLAYERS];
new g_LastTick[MAX_PLAYERS];
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `MapAndreas_Init` "succeeds" but every Z is 0 | checked `if (!init)` while 0 means success, so the failure was ignored | compare with `MAP_ANDREAS_ERROR_SUCCESS` and log the code |
| Interior floor returns street height | MapAndreas is terrain only | skip it when interior != 0, use `CA_FindZ_For2DCoord` |
| Raycast misses a custom object | collision never registered server-side | `CA_CreateObject` / `CA_CreateDynamicObject_DC` at the same transform |
| Player falls through a mapped floor | object created after `CA_Init` without a collision entry | register with the wrapper, or place before init for static maps |
| Invisible walls where buildings were removed | `CA_RemoveBuilding` called after `CA_Init` | removal before init, restore after |
| Server tick time doubles after enabling | raycast per player per tick | quantised cell cache, one sample per second per player |
| `libBulletCollision.so` missing on Linux | plugin built against Bullet 2.82 | use the static `.so`, or install the i386 Bullet libs |

## Verification

```bash
ldd plugins/ColAndreas.so | grep -i bullet || echo "static build (no bullet dep)"
```

```text
	libBulletCollision.so.2.82 => /usr/lib/i386-linux-gnu/libBulletCollision.so.2.82
	libBulletDynamics.so.2.82 => /usr/lib/i386-linux-gnu/libBulletDynamics.so.2.82
```

- A dynamic build lists both libraries and they resolve; `not found` on either line
  is the crash at plugin load.
- In game, `/ztest` above the LS airport prints
  `mapandreas=14.32 colandreas=14.10`, values within a metre of each other; inside
  a mapped interior it prints `mapandreas=14.32 colandreas=1.02` or `colandreas=nan`
  when nothing is under the ray.
- `CA_RayCastLine` through a newly mapped wall returns 1 and a hit point within
  0.1 of the wall plane; the same call before registration returns 0.

## Sources (2026)

- https://github.com/philip1337/samp-plugin-mapandreas
- https://github.com/Pottus/ColAndreas
- https://github.com/Pottus/ColAndreas/wiki/Using-the-Plugin
