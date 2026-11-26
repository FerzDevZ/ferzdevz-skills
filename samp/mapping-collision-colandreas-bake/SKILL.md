---
name: mapping-collision-colandreas-bake
description: Use when custom map geometry has no collision.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, colandreas]
    category: samp
---

# Bake collision for a custom map instead of trusting the visual mesh

The client renders your custom building; the server only knows numbers you give it. ColAndreas
simulates the stock San Andreas world plus what you register, MapAndreas knows terrain height and
nothing else, and a custom model id is in neither dataset. The durable answer is a baked grid.

## When to Use

- Players walk through custom walls, or fall through a custom floor into the void.
- `CA_RayCastLine` returns 0 at a spot where the object is obviously present.
- Twenty players in one custom interior exhaust the raycast budget you spent per tick.
- `MapAndreas_FindZ_For2DCoord` reports sea level under an interior that sits at z = 1500.

## Compatibility & Stack Matrix (2026)

| Layer | Data it holds | Knows custom models | Cost per query | Use it for |
| --- | --- | --- | --- | --- |
| Client physics | the model's own COL | yes, client only | zero on the server | nothing you enforce server-side |
| MapAndreas 1.2.1 | 1 m terrain heightmap | no, terrain only | one lookup | terrain height, airbreak checks |
| ColAndreas | SA object collision + objects registered at boot | only through a stock proxy model | a real raycast, thousands per second at best | probes, spawn points, bullets |
| Baked grid | floats you precomputed | yes, whatever the map held when you baked | one array index | per-tick ground, door and zone checks |

`CA_RayCastLine` returns 0 for "no hit", the water constant for water, and otherwise the model id it
hit. Treat anything `<= 0` as no ground: a ray starting inside geometry also returns 0, which is why
the bake fires from above the map. `ColAndreas.cadb` lives in `scriptfiles/ColAndreas/`; `CA_Init`
returns 0 when it is absent.

## Production Implementation

1. Pair every custom model with a stock proxy whose collision is close enough. A custom model id is
   not in the SA collision data, so rays pass through it; the proxy is what the simulation collides
   with. Ids come from the SA object list, never from memory:

```pawn
#define PROXY_WALL  19483       // stock model with a solid vertical face
#define PROXY_FLOOR 19379       // stock model with a flat top

enum E_PROXY { PROXY_MODEL, PROXY_SRC, Float:P_X, Float:P_Y, Float:P_Z, Float:P_RZ }

new const g_Proxies[][E_PROXY] =
{
    {PROXY_WALL,  19999, 1420.5, -1710.5, 12.0, 90.0},
    {PROXY_FLOOR, 19998, 1420.5, -1710.5, 11.8,  0.0}
};
```

2. Get the boot order right, because two of the three calls fail quietly when it is wrong:

```pawn
public OnGameModeInit()
{
    ColRemovals_Apply();            // CA_RemoveBuilding, before init
    if (!CA_Init()) { print("COLBAKE: ColAndreas.cadb missing"); return 0; }
    ColProxies_Register();          // objects enter the simulation after init
    ColRemovals_Restore();          // CA_RestoreBuilding, after init
    return 1;
}
```

3. Bake a grid over the map bounds, not the whole world. Size the array before writing the loop:
   400 x 400 cells at 1.5 m is 640 KB of AMX data; 2000 x 2000 would be 16 MB and will not fit:

```pawn
#define BAKE_CELL   1.5
#define BAKE_W      400
#define BAKE_H      400
#define BAKE_EMPTY  -9999.0

new Float:g_BakeZ[BAKE_W * BAKE_H];
new Float:g_BakeMinX, g_BakeMinY;

stock Bake_Run()
{
    new hits, misses, Float:hx, Float:hy, Float:hz;
    for (new gy = 0; gy < BAKE_H; gy++)
    for (new gx = 0; gx < BAKE_W; gx++)
    {
        new Float:x = g_BakeMinX + float(gx) * BAKE_CELL;
        new Float:y = g_BakeMinY + float(gy) * BAKE_CELL;
        new model = CA_RayCastLine(x, y, 200.0, x, y, -50.0, hx, hy, hz);
        if (model > 0) { g_BakeZ[gy * BAKE_W + gx] = hz; hits++; }
        else           { g_BakeZ[gy * BAKE_W + gx] = BAKE_EMPTY; misses++; }
    }
    printf("COLBAKE cells=%d hits=%d misses=%d", BAKE_W * BAKE_H, hits, misses);
    return hits;
}
```

4. Store it with a header, so a stale or truncated file is rejected instead of read as geometry:

```pawn
stock Bake_Save(const path[])
{
    new File:f = fopen(path, io_write), header[4] = {0x314C4243, 1, BAKE_W, BAKE_H};
    if (!f) { printf("COLBAKE cannot write %s", path); return 0; }   // 'CBL1', version, w, h
    fblockwrite(f, header, sizeof header);
    fblockwrite(f, g_BakeZ, sizeof g_BakeZ);
    fclose(f);
    return 1;
}
```

5. Answer ground queries from the grid, and fall back to a live ray only for the cells the bake
   missed (doors, moving objects, the map edge):

```pawn
stock bool:GroundAt(Float:x, Float:y, &Float:z)
{
    new gx = floatround((x - g_BakeMinX) / BAKE_CELL);
    new gy = floatround((y - g_BakeMinY) / BAKE_CELL);
    if (gx >= 0 && gy >= 0 && gx < BAKE_W && gy < BAKE_H)
    {
        z = g_BakeZ[gy * BAKE_W + gx];
        if (z != BAKE_EMPTY) return true;
    }
    new Float:hx, Float:hy;
    return CA_RayCastLine(x, y, 200.0, x, y, -50.0, hx, hy, z) > 0;
}
```

6. Probe the perimeter after every map change and log each miss. A west wall that misses is a hole
   players will find; version the bake against the map hash so a stale grid cannot ship:

```pawn
stock bool:ColProbePoint(Float:x, Float:y)
{
    new Float:hx, Float:hy, Float:hz;
    return CA_RayCastLine(x, y, 200.0, x, y, -50.0, hx, hy, hz) > 0;
}
```

   Sample the four corners and the midpoint of each edge — any 0 is a hole. Then store the map file
   hash in the bake header and refuse to boot when it differs.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every raycast returns 0 | bake ran before `CA_Init`, or the cadb was never generated | init first, check the `CA_Init` return value |
| Removed buildings still block rays | `CA_RemoveBuilding` called after init | removals before `CA_Init`, restores after it |
| Custom walls pass rays through | no proxy registered, custom model id unknown to the simulation | register a stock proxy at the same transform |
| Server refuses the AMX or dies on boot | grid array sized over the whole world | bound the grid to the map, 640 KB at 400 x 400 |
| Player lands at sea level in an interior | `MapAndreas` used as a floor lookup | MapAndreas is terrain only; use the bake |
| Baked map walks through a new wall | grid not rebuilt after the map edit | hash the map file, rebuild on change |

## Verification

```bash
stat -c '%s' /opt/omp-server/scriptfiles/colbake/interior.bin
```

Expected: `640016` bytes — 16 bytes of header plus 400 x 400 floats at 4 bytes. In the log,
`COLBAKE cells=160000 hits=` must be non-zero, twelve `ColProbePoint` samples per building must all
return 1 (a 0 is a hole), and `COLPROXY registered=` must equal the custom object count.
## Sources (2026)

- https://github.com/Pottus/ColAndreas
- https://github.com/Pottus/ColAndreas/wiki/Functions
- https://github.com/Pottus/ColAndreas/wiki/Instructions
