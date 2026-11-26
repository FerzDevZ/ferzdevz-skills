---
name: modular-map-file-parser-cfg-json
description: Use when map data lives in a file, not the script.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, parser]
    category: samp
---

# A map file parser with a declared count and a reject log

## When to Use

- A 20k-object map sits in a `.pwn` include and every tweak needs a recompile.
- Designers export map data and nobody can tell whether all rows loaded.
- You want `/mapreload` that swaps the live map without a restart.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `fopen`/`fread`/`fwrite`/`fseek`/`fclose` in core |
| file root | `scriptfiles/` | `fopen` cannot leave that folder; paths are relative |
| streamer | 2.9.6 | `CreateDynamicObject`, `DestroyDynamicObject`, `IsValidDynamicObject` |
| parsing | sscanf2 2.15.1 | `"iffffffdd"` = int, 6 floats, 2 ints; non-zero means reject |
| format | line-per-record JSON array subset | `[model,x,y,z,rx,ry,rz,world,interior],` |
| header | `# map <name> v1 count=<n>` | the count is the contract, not a comment |

## Production Implementation

1. Fix the format in writing: header, one record per line, nine fields, trailing comma allowed, `#` starts a comment.
2. Normalise each line before sscanf: leading `[`, trailing `],`, whitespace and the `\r` from a CRLF export all have to go.
3. Parse into a staging array and compare the accepted count with the header. Commit only on a match, so a truncated upload cannot replace a working map.
4. Validate ranges as data: a positive model id and coordinates inside the map bounds. Rejects are logged with their line number.

```text
# map docks v1 count=3
[1337,1234.5,-1500.2,20.0,0.0,0.0,0.0,0,0]
```

```pawn
#include <open.mp>
#include <streamer>
#include <sscanf2>

#define MAP_MAX_ROWS (20000)
#define MAP_BOUND    (3000.0)
#define MAP_MIN_Z    (-100.0)
#define MAP_MAX_Z    (1000.0)

enum E_MAP_ROW
{
    mapModel, Float:mapX, Float:mapY, Float:mapZ,
    Float:mapRX, Float:mapRY, Float:mapRZ, mapWorld, mapInterior
};

new gRows[MAP_MAX_ROWS][E_MAP_ROW];
new gObjects[MAP_MAX_ROWS];
new gRowCount, gRejectCount, gCreateIdx, gMapTimer = -1;

stock TrimRecord(line[])
{
    new start, end = strlen(line);
    while (line[start] == ' ' || line[start] == '\t' || line[start] == '[') start++;
    while (end > start && (line[end - 1] == ' ' || line[end - 1] == '\t' ||
           line[end - 1] == '\r' || line[end - 1] == ',' || line[end - 1] == ']')) end--;
    if (start) strdel(line, 0, start);
    line[end - start] = '\0';
    return end - start;
}

stock MapHeaderCount(const line[])
{
    new pos = strfind(line, "count=");
    return (pos == -1) ? -1 : strval(line[pos + 6]);
}

stock bool:MapParse(const file[])
{
    if (!fexist(file)) { printf("[map] missing %s", file); return false; }
    new File:f = fopen(file, io_read);
    if (!f) { printf("[map] cannot open %s", file); return false; }

    new line[192], lineno, parsed, declared = -1;
    gRejectCount = 0;

    while (fread(f, line))
    {
        lineno++;
        if (line[0] == '#') { new n = MapHeaderCount(line); if (n >= 0) declared = n; continue; }
        if (TrimRecord(line) == 0) continue;

        new model, world, interior;
        new Float:x, Float:y, Float:z, Float:rx, Float:ry, Float:rz;

        if (parsed >= MAP_MAX_ROWS
            || sscanf(line, "iffffffdd", model, x, y, z, rx, ry, rz, world, interior)
            || model <= 0
            || x < -MAP_BOUND || x > MAP_BOUND || y < -MAP_BOUND || y > MAP_BOUND
            || z < MAP_MIN_Z || z > MAP_MAX_Z)
        {
            printf("[map] reject line=%d field count, model or coordinate", lineno);
            gRejectCount++;
            continue;
        }

        gRows[parsed][mapModel] = model, gRows[parsed][mapWorld] = world, gRows[parsed][mapInterior] = interior;
        gRows[parsed][mapX] = x, gRows[parsed][mapY] = y, gRows[parsed][mapZ] = z;
        gRows[parsed][mapRX] = rx, gRows[parsed][mapRY] = ry, gRows[parsed][mapRZ] = rz;
        parsed++;
    }
    fclose(f);

    printf("[map] parsed=%d declared=%d rejects=%d", parsed, declared, gRejectCount);
    if (declared >= 0 && parsed != declared)
    {
        printf("[map] count mismatch, keeping the running map");
        return false;
    }
    gRowCount = parsed;
    printf("[map] reload queued rows=%d", gRowCount);
    return true;
}

stock MapDestroy(count)
{
    for (new r = 0; r < count; r++)
        if (IsValidDynamicObject(gObjects[r])) DestroyDynamicObject(gObjects[r]);
}

stock bool:MapReload(const file[])
{
    new old = gRowCount;                    // capture before MapParse commits the new count
    if (!MapParse(file)) return false;      // failed parse leaves the live map untouched
    MapDestroy(old);
    gCreateIdx = 0;
    if (gMapTimer != -1) KillTimer(gMapTimer);
    gMapTimer = SetTimer("MapCreateChunk", 20, true);
    return true;
}
```

5. Create the objects from `gRows` in a `MapCreateChunk` timer, 50 per 20 ms, storing each handle in `gObjects` and stopping the timer when `gCreateIdx == gRowCount`. Wire `/mapreload` to `MapReload` so the command and the boot path cannot diverge.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| last field of every row shifted | header or separator counted as data | strip `[` `]` `,` first, check the sscanf return |
| half the map missing, no error | truncated export, count header ignored | compare `parsed` with `declared`, refuse the load |
| objects vanish after a bad reload | old set destroyed before the new parse finished | parse to staging, destroy only on success |
| a few objects at 0,0,0 | empty fields parsed as zeros | range check rejects them into the log |
| server freezes on reload | every row created in one pass | 50 per 20 ms tick, stop the timer at the end |

## Verification

```bash
awk 'NR==1{split($0,a,"count="); print "declared=" a[2]} NR>1 && $0 ~ /^[[:space:]]*\[/ {n++} END{print "records=" n}' scriptfiles/maps/docks.map
```

Expected on the sample file: `declared=3` and `records=3`. A different pair means the header is stale and boot will print `count mismatch`.

Boot log on a clean load must read `[map] parsed=3 declared=3 rejects=0`, then `[map] reload queued rows=3`; your chunk timer then reports `created=3`. Any `[map] reject line=…` line names the row to fix at the source.

## Sources (2026)

- [open.mp — fopen](https://open.mp/docs/scripting/functions/fopen) — modes, the `scriptfiles` root, and the NULL handle that crashes on use in SA-MP.
- [sscanf 2.15.1 include](https://raw.githubusercontent.com/maddinat0r/sscanf/master/sscanf2.inc) — specifier list and the non-zero return that marks a rejected record.
