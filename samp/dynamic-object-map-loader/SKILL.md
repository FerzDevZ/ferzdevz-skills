---
name: dynamic-object-map-loader
description: Use when streamed map objects half-load or never appear.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, streamer]
    category: samp
---

# Load a large object map in ticks, then prove the count

## When to Use

- A streamed map loads on the server but half the objects never appear for players.

- `OnGameModeInit` blocks for seconds or minutes while thousands of objects are created.
- The map is partly missing after a restart, with no error in the log.
- A map export (Texture Studio, Fusez, custom tool) has to become live objects without a recompile.
- Not for a handful of hand-written objects; a literal array in the script is cheaper and safer there.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `CreateDynamicObject` comes from the plugin, not the core |
| SA-MP native objects | 1000 global, 1000 per player (0.3.7) | `CreateObject` cannot carry a 10k map |
| streamer | 2.9.6, `Streamer_GetMaxItems` default -1 | no pool cap until you set one |
| streamer tick | 50 ms; object chunk tick 1 | each tick rechecks object cells, so creation bursts are felt |
| file i/o | Pawn `fopen`/`fread`/`fseek`/`fclose` | ships with the compiler, no library needed |
| parsing | sscanf2 2.15.1 | `"iffffffddff"`, no `%` prefixes |

Rows are whitespace separated, one object per line: `model x y z rx ry rz world interior stream draw`. Comments start with `#`. Keeping the file line-oriented is what makes the count check possible.

## Production Implementation

1. Export to a line file and count it before the server ever reads it:

```bash
awk -F, 'NF == 11 {print $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11}' export.csv > maps/ls_docks.map
grep -vc '^\s*#\|^\s*$' maps/ls_docks.map
```

2. Parse the file in one pass at boot, count the rows, then let a timer create them. Parsing 10k lines is cheap; creating 10k objects is not.

```pawn
#include <open.mp>
#include <streamer>
#include <sscanf2>

#define MAP_FILE   "maps/ls_docks.map"
#define MAP_BATCH  (100)
#define MAP_PERIOD (20)

new File:gMapFile;
new gMapTimer = -1;
new gMapRows;       // rows counted in pass 1
new gMapCreated;    // objects created so far
new gMapBad;        // rows rejected by sscanf

forward MapChunk();

stock MapLoadBegin()
{
    if (!fexist(MAP_FILE)) { printf("[map] missing %s", MAP_FILE); return 0; }

    gMapFile = fopen(MAP_FILE, io_read);
    if (!gMapFile) return 0;

    new line[160];
    while (fread(gMapFile, line))
    {
        if (line[0] == '#' || line[0] == '\0') continue;
        gMapRows++;
    }

    fseek(gMapFile, 0);
    printf("[map] %d rows queued from %s", gMapRows, MAP_FILE);
    gMapTimer = SetTimer("MapChunk", MAP_PERIOD, true);
    return 1;
}
```

3. Create a bounded batch per tick and stop on the row count. Pawn has no `feof`, so a batch that reads nothing is the end-of-file signal:

```pawn
public MapChunk()
{
    new line[160], done;

    while (done < MAP_BATCH && fread(gMapFile, line))
    {
        if (line[0] == '#' || line[0] == '\0') continue;
        done++;

        new model, world, interior, Float:sd, Float:dd;
        new Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz;

        if (sscanf(line, "iffffffddff", model, x, y, z, rx, ry, rz, world, interior, sd, dd))
        {
            gMapBad++;
            continue;
        }

        CreateDynamicObject(model, x, y, z, rx, ry, rz, world, interior, -1, sd, dd);
        gMapCreated++;
    }

    if (done > 0 && gMapCreated + gMapBad < gMapRows)
        return;                              // rows left, keep ticking

    KillTimer(gMapTimer);
    fclose(gMapFile);
    gMapTimer = -1;

    printf("[map] created %d/%d objects (%d bad rows)", gMapCreated, gMapRows, gMapBad);
}
```

4. Start it from init; `gMapTimer == -1 && gMapCreated == gMapRows` is the gate gameplay code checks before it runs:

```pawn
public OnGameModeInit()
{
    MapLoadBegin();
    return 1;
}
```

5. Cross-check the plugin side once, not per item. `Streamer_GetUpperBound` is include-only (it is not in the server native allowlist), so it needs `streamer.inc`:

```pawn
printf("[map] upper bound %d for %d created", Streamer_GetUpperBound(STREAMER_TYPE_OBJECT), gMapCreated);
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| server freezes at start, then works | every object created synchronously in `OnGameModeInit` | create from a repeating timer, 100 per 20 ms |
| map is 60-90% there after a restart | parse error dropped rows without a log line | count `gMapBad` and print it |
| objects exist but only some players see them | `worldid`/`interiorid` in the file do not match the players' state | export the ids you actually use, or -1 for global |
| clients hitch while the map loads | batch too large for one tick | lower `MAP_BATCH`, raise `MAP_PERIOD` |
| `error 017: undefined symbol feof` | Pawn's file API has no `feof` | stop when a batch reads zero rows |
| map differs between servers with the same build | the file is outside version control | ship `maps/` with the gamemode, check `fexist` at boot |

## Verification

Expected count first, from the shell:

```bash
grep -vc '^\s*#\|^\s*$' maps/ls_docks.map
```

Take that number (for example `10240`) and compare it with the boot log, which must print `[map] 10240 rows queued`, then `[map] created 10240/10240 objects (0 bad rows)`, then `[map] upper bound 10240 for 10240 created`.

A mismatch in any of the three numbers is the bug: rows queued vs created means a parse problem, upper bound vs created means the plugin rejected creations. Compile check:

```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```

Expected: `0 Errors` and `0 Warnings`.

## Sources (2026)

- [open.mp limits](https://open.mp/docs/scripting/resources/limits) — 1000 global and per-player objects in 0.3.7.
- [streamer.inc 2.9.6](https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/streamer.inc) — `CreateDynamicObject` signature, `Streamer_GetUpperBound`, per-type stream-distance defaults.
- [samp-incognito/samp-streamer-plugin](https://github.com/samp-incognito/samp-streamer-plugin) — release line and include ownership (not part of omp-stdlib).
