---
name: 3d-text-label-streaming
description: Use when 3D labels pop in, flicker or blow the pool.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer, 3dtext, performance]
    category: samp
---

# Stream 3D labels from one table under a per-player budget

A label costs a client round trip when it enters the stream radius, and the native pool
is 1024 entries whether or not a streamer is installed. The failure is rarely "too many
labels": it is a draw distance larger than the stream distance, a label rebuilt on every
text change, or a per-player visibility cap left at the streamer default.

## When to Use

- Labels appear in visible steps instead of at a fixed distance (pop-in).
- FPS drops only in markets, spawn areas or parking lots.
- `CreateDynamic3DTextLabel` starts returning an invalid id at boot.
- Sign text is destroyed and recreated whenever a price or timer changes.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 (0.3.7-R2 compatible) | native labels, same pools |
| Streamer | 2.9.6, `#include <streamer>` | provides `CreateDynamic3DTextLabel` |
| Global label pool | 1024 (`MAX_3DTEXT_GLOBAL`) | streamer items sit on top, they do not raise it |
| Per-player label pool | 1024 (`MAX_3DTEXT_PLAYER`) | `CreatePlayer3DTextLabel` |
| `STREAMER_3D_TEXT_LABEL_SD` | 200.0 | default `streamdistance` when omitted |
| `STREAMER_TYPE_3D_TEXT_LABEL` | 5 | type id used by `Streamer_SetVisibleItems` |
| `testlos` argument | 0 = visible through walls | pass 1 for interior signs |

The two distances are separate budgets. `drawdistance` is where the text starts to fade
client side; `streamdistance` is when the server hands the item over. If `streamdistance`
is smaller, the label is removed while still inside its own draw radius and the fade
never completes — the classic "it blinks out" report.

## Production Implementation

1. Keep the label set in one file and load it once at boot. Each row carries both
   distances and both dimension ids; a row whose stream distance is below its draw
   distance is clamped, not silently accepted:

```pawn
#include <openmp>
#include <sscanf2>
#include <streamer>

#define MAX_LABELS (512)
#define LABEL_TEXT_LEN (128)

enum E_Label
{
    lbName[24], Float:lbX, Float:lbY, Float:lbZ, lbWorld, lbInterior,
    Float:lbDraw, Float:lbStream, lbTestLos, lbId
};

new gLabel[MAX_LABELS][E_Label];
new gLabelCount;

stock LabelLoad(const file[])
{
    new File:f = fopen(file, io_read), line[160];
    if (!f) { printf("[labels] %s missing", file); return 0; }
    while (fread(f, line) && gLabelCount < MAX_LABELS)
    {
        if (line[0] == '#' || line[0] == '\0') continue;
        if (sscanf(line, "s[24]fffddffd", gLabel[gLabelCount][lbName],
                   gLabel[gLabelCount][lbX], gLabel[gLabelCount][lbY],
                   gLabel[gLabelCount][lbZ], gLabel[gLabelCount][lbWorld],
                   gLabel[gLabelCount][lbInterior], gLabel[gLabelCount][lbDraw],
                   gLabel[gLabelCount][lbStream], gLabel[gLabelCount][lbTestLos]))
            continue;                       // malformed row never reaches the pool
        if (gLabel[gLabelCount][lbStream] < gLabel[gLabelCount][lbDraw])
            gLabel[gLabelCount][lbStream] = gLabel[gLabelCount][lbDraw];
        gLabel[gLabelCount][lbId] = -1;
        gLabelCount++;
    }
    fclose(f);
    printf("[labels] %d definitions loaded", gLabelCount);
    return 1;
}
```

2. Create every label through one stock, so the argument order lives in one place.
   Positional: `attachedplayer`, `attachedvehicle`, `testlos`, `worldid`, `interiorid`,
   `playerid`, `streamdistance` follow the draw distance; the rest keeps its default:

```pawn
stock LabelSpawnAll()
{
    new text[LABEL_TEXT_LEN], created;
    for (new i = 0; i < gLabelCount; i++)
    {
        format(text, sizeof text, "%s", gLabel[i][lbName]);
        gLabel[i][lbId] = _:CreateDynamic3DTextLabel(text, 0xFFFFFFFF,
            gLabel[i][lbX], gLabel[i][lbY], gLabel[i][lbZ], gLabel[i][lbDraw],
            INVALID_PLAYER_ID, INVALID_VEHICLE_ID, gLabel[i][lbTestLos],
            gLabel[i][lbWorld], gLabel[i][lbInterior], -1, gLabel[i][lbStream]);
        if (gLabel[i][lbId] != -1) created++;
    }
    printf("[labels] %d/%d created", created, gLabelCount);
    return created;
}
```

3. Change text in place. `UpdateDynamic3DTextLabelText` keeps the id, so the client
   never drops and re-adds the item — a destroy/create pair on a 1 Hz timer is exactly
   what produces the visible flicker:

```pawn
stock LabelSetText(idx, const text[], colour = 0xFFFFFFFF)
{
    if (idx < 0 || idx >= gLabelCount || gLabel[idx][lbId] == -1) return 0;
    UpdateDynamic3DTextLabelText(STREAMER_TAG_3D_TEXT_LABEL:gLabel[idx][lbId], colour, text);
    return 1;
}
```

4. Cap what one client may hold. The third argument of `Streamer_SetVisibleItems` is the
   player id, so this is a per-player ceiling for one type instead of a server-wide one:
   `Streamer_SetVisibleItems(STREAMER_TYPE_3D_TEXT_LABEL, 120, playerid)`. Read it back
   with `Streamer_GetVisibleItems(STREAMER_TYPE_3D_TEXT_LABEL, playerid)` in `/labelstat`.

5. Door signs readable at the craft bench get 15 to 25 units; map-board plates get 8 to 12.

6. On unload, call `DestroyDynamic3DTextLabel` once per id in the table, then reset `lbId`.

7. For per-player content (a balance plate over an ATM), pass the `playerid` argument:
   `-1` is everyone, a real id is one client. Sharing one label leaks another's price.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Label vanishes before its fade ends | `streamdistance` below `drawdistance` | clamp stream to at least draw at load |
| Flicker once per second | destroy + recreate on each update | `UpdateDynamic3DTextLabelText` on the same id |
| Visible through interior walls | `testlos` left at 0 | pass 1 as the ninth argument |
| Creation fails at boot | more than 1024 labels, or the include missing | move static geography to material-text signs, split by area |
| Street full of labels at spawn | per-player cap at the streamer default | `Streamer_SetVisibleItems(STREAMER_TYPE_3D_TEXT_LABEL, 120, playerid)` |
| Text shows another player's data | one global label reused per player | pass the `playerid` argument or use `CreatePlayer3DTextLabel` |
| Labels from world 0 show in an interior | `worldid` passed as -1 (wildcard) | pass the real world and interior id |

## Verification

Distance pairs are checked before the gamemode starts, so no bad row reaches
`CreateDynamic3DTextLabel`:

```bash
awk 'NF && $1 !~ /^#/ { if ($8 < $7) {print "stream<draw", $1; bad++} if ($7 > 30) {print "draw>30", $1; bad++} n++ } END { print (bad ? "FAIL" : "labels ok"), n, "rows" }' labels.cfg
```

Expected on a healthy table:

```text
labels ok 34 rows
```

In game, `/labelstat` prints the per-player cap plus the labels inside `streamdistance`.

## Sources (2026)

- https://open.mp/docs/scripting/resources/limits — 1024 global and 1024 per-player 3D labels; streamers exist to bypass entity limits.
- https://open.mp/docs/scripting/functions/Create3DTextLabel — invalid id on pool exhaustion, `testLOS`, and `virtualWorld -1` never appearing.
- https://github.com/samp-incognito/samp-streamer-plugin — streamer 2.9.6 source, `streamer.inc` signatures and `INVALID_STREAMER_ID`.
