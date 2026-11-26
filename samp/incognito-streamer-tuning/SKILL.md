---
name: incognito-streamer-tuning
description: Use when objects pop in late or streamer CPU grows.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer, performance]
    category: samp
---

# Tune streamer distances, visibility caps and grid settings

## When to Use

- Props appear a few metres away, or only once the player stops moving.
- CPU climbs with map size even while nobody is near the dense district.
- One global `streamdistance` was applied to 10k items and never measured since.
- You are about to raise visible items and want the real cap before touching it.
- Do not use this for missing objects that never load at all; that is a loader or count bug, not a tuning one.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | streamer is a legacy plugin: `pawn.legacy_plugins: ["streamer"]` |
| streamer plugin | 2.9.6 (`Streamer_IncludeFileVersion` 0x296) | Windows `.dll` and Linux `.so` must match the server build |
| include | `streamer.inc` from the same release | every `Streamer_*` native below comes from it, not from omp-stdlib |
| streamer tick | 50 ms, object chunk tick 1 | `Streamer_GetTickRate`, `Streamer_GetChunkTickRate` |
| grid | cell size 300.0, cell distance 360000.0 | the distance is stored squared, i.e. 600 m |

Defaults from the 2.9.6 source, not from memory: visible items are 500 objects, 4096 pickups, 100 map icons, 1024 3D labels, 1000 actors; `Streamer_GetMaxItems` reads as `-1` (no cap) until you set one; stream distance is 300.0 for objects and 200.0 for every other type; draw distance is 0.0, meaning no client override.

## Production Implementation

1. Read the current budget before changing anything:

```pawn
new maxitems = Streamer_GetMaxItems(STREAMER_TYPE_OBJECT);      // -1 = unlimited
new visible  = Streamer_GetVisibleItems(STREAMER_TYPE_OBJECT);  // 500 by default
new Float:cell, Float:cellDist;

Streamer_GetCellSize(cell);
Streamer_GetCellDistance(cellDist);
printf("[streamer] objects max=%d visible=%d cell=%.0f celldist=%.0f", maxitems, visible, cell, cellDist);
```

2. Set distance per item at creation. `streamdistance` is what the server keeps resident for the player; `drawdistance` is what the client renders. Small props 60-100 m, district geometry 150-250 m, skyline landmarks 400 m and up.

```pawn
CreateDynamicObject(19483, x, y, z, 0.0, 0.0, 0.0, WORLD_LS, INTERIOR_NONE, -1, 150.0, 150.0);
```

3. Raise visibility only for the type that needs it, and only after measuring the current value. `Streamer_SetMaxItems` is a pool guard, not a visibility cap; raising it alone changes nothing on screen.

```pawn
// 500 objects is the shipped default; 700 is a deliberate, measured raise.
Streamer_SetVisibleItems(STREAMER_TYPE_OBJECT, 700);
```

4. Cut re-stream work on objects, which are the expensive type. The object chunk tick is 1 by default, so every streamer tick rechecks the player's object cells; 2 halves that at the cost of one tick of latency.

```pawn
Streamer_SetChunkTickRate(STREAMER_TYPE_OBJECT, 2);
```

5. Change the grid only with a reason. `Streamer_SetCellSize` and `Streamer_SetCellDistance` rebuild the grid immediately, so they are safe at runtime but cost one rebuild; a smaller cell means more cells and more per-tick bookkeeping, not fewer items.

```pawn
Streamer_SetCellSize(250.0);        // rebuilds the grid, then re-streams everyone
```

6. Measure the result per player instead of trusting the global value. `Streamer_CountVisibleItems` is include-only (it is not in the server native allowlist), so it needs `streamer.inc` in the build:

```pawn
printf("[streamer] player %d sees %d objects", playerid, Streamer_CountVisibleItems(playerid, STREAMER_TYPE_OBJECT, 1));
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| objects vanish at 300 m on a server where nothing was configured | object stream distance default is 300.0 with draw distance 0.0 | pass explicit stream and draw distance at creation |
| raising `Streamer_SetMaxItems` changes nothing visually | max items is a pool guard; visibility is `Streamer_SetVisibleItems` | set the visible cap for the type, then measure |
| world objects flicker only on low-FPS clients | visible object count above what the client can draw at that distance | shorten distances first, then raise the cap |
| CPU unchanged after `Streamer_SetTickRate(50)` | objects are re-streamed on the chunk tick, not the global tick | set `Streamer_SetChunkTickRate(STREAMER_TYPE_OBJECT, 2)` |
| distant district still costs CPU | cell distance 600 m keeps far items in the same grid cells | shorten stream distance; shrink cells only after that |
| objects from another world leak in after tuning | `worldid`/`interiorid` left at -1 on items that should be local | set both ids per item |

## Verification

Compile with warnings as errors, then read the startup line:

```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```

Expected: `Header size: ...` followed by `0 Errors` and `0 Warnings`. At boot the probe must print the shipped defaults:

```text
[streamer] objects max=-1 visible=500 cell=300 celldist=360000
```

Then walk the densest district for 30 s and run `/streamstats`: `Streamer_CountVisibleItems` should hold steady near the cap instead of oscillating, and `top` should show the server thread below its pre-tuning load. Confirm the natives you rely on exist in the allowlist before shipping:

```bash
grep -w -e Streamer_SetVisibleItems -e Streamer_GetVisibleItems samp/samp-dev-router/assets/omp_natives.txt
```

## Sources (2026)

- [samp-incognito/samp-streamer-plugin](https://github.com/samp-incognito/samp-streamer-plugin) — 2.9.6 release, README, plugin-vs-include split.
- [src/data.cpp](https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/src/data.cpp) — visible-item defaults per type (500/4096/100/1024/1000), unlimited `globalMaxItems`.
- [open.mp config.json](https://open.mp/docs/server/config.json) — `pawn.legacy_plugins` example `["mysql", "streamer"]`.
