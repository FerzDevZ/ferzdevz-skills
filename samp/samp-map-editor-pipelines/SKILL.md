---
name: samp-map-editor-pipelines
description: Use when map editor output must become streamed code.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, mapping, streamer, texture-studio, objects]
    category: samp
---

# Turn map editor output into streamer code that matches the count

## When to Use

- A map was built in Texture Studio, Fusez Map Editor V3 or Ultimate Creator and has to ship as code.
- A converted map has objects that never stream in, flicker at distance, or lose their textures.
- Stock buildings still show through a custom interior.
- You are about to hand-edit a 4000-line export and want the mechanical part scripted.
- Not for baking collision for those objects; that is `mapping-collision-colandreas-bake`.

## Compatibility & Stack Matrix (2026)

| Editor | Save command | What the file contains | What must be rewritten |
| --- | --- | --- | --- |
| Texture Studio | `/export` (after `/loadmap`) | `CreateDynamicObjectEx(...)` or `CreateDynamicObject(...)`, chosen at export | nothing if sold streamer code; re-check the distance args |
| Texture Studio import | `/importmap` | accepts raw `CreateObject()` or `CreateDynamicObject()` code | use it to bring legacy maps in |
| Fusez Map Editor V3 | map save to `scriptfiles` | `new g_Object[N];`, `g_Object[i] = CreateObject(...); //comment`, `SetObjectMaterial(g_Object[i], ...)` | `CreateObject` to `CreateDynamicObject`, `SetObjectMaterial` to `SetDynamicObjectMaterial` |
| Ultimate Creator | save to `scriptfiles` (`.txt` by default) | `//Removed objects` block with `RemoveBuildingForPlayer`, then `//Objects` block | same object rewrite, plus replaying the removals per player |
| MapFix | filterscript | stock-map texture fixes | load it before your map, never after |

## Production Implementation

1. Export once and commit the raw file. The export is the source of truth; the generated `.pwn` is a build
   artefact you can regenerate, never hand-tune.

2. Rewrite the mechanical part with a script. This converter was run against a Fusez export and a
   hand-written `CreateObject` block; it keeps comments as object labels and fails loudly on odd lines:

```python
import re, sys

OBJ = re.compile(r'^(\s*)(g_\w+\[(\d+)\]\s*=\s*)?CreateObject\(([^;]*)\);\s*(?://\s*(.*))?$')
MAT = re.compile(r'^(\s*)SetObjectMaterial\((g_\w+\[\d+\]),\s*(\d+),\s*(\d+),'
                 r'\s*"([^"]*)",\s*"([^"]*)",\s*(0x[0-9A-Fa-f]+)\);')

def main(src, dst):
    out, n_obj, n_mat, missed = [], 0, 0, 0
    for line in open(src, encoding="utf-8", errors="replace"):
        line = line.rstrip("\r\n")
        m = OBJ.match(line)
        if m and len(m.group(4).split(",")) == 7:
            i, lhs = m.group(1), m.group(2) or ""
            a = [x.strip() for x in m.group(4).split(",")]
            c = f' // {m.group(5)}' if m.group(5) else ""
            out.append(f'{i}{lhs}CreateDynamicObject({", ".join(a)}, -1, -1, -1, 300.0, 300.0);{c}')
            n_obj += 1
            continue
        m = MAT.match(line)
        if m:
            g = m.groups()
            out.append(f'{g[0]}SetDynamicObjectMaterial({g[1]}, {g[2]}, {g[3]}, "{g[4]}", "{g[5]}", {g[6]});')
            n_mat += 1
            continue
        if "CreateObject(" in line or "SetObjectMaterial(" in line:
            missed += 1
        out.append(line)
    open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print(f"objects={n_obj} materials={n_mat} unhandled={missed}")

main(sys.argv[1], sys.argv[2])
```

3. Replay removals per player, before anything streams. A removal applied at boot only sticks for
   whichever player existed then, and the 1000-removal budget per player is silent when exceeded:

```pawn
new const g_Removals[][4] = {
    {19475, 100.5000, 200.2500, 10.0000},
    {19476, 110.5000, 200.2500, 10.0000}
};

public OnPlayerConnect(playerid)
{
    for (new i = 0; i < sizeof g_Removals; i++)
    {
        RemoveBuildingForPlayer(playerid, g_Removals[i][0], g_Removals[i][1],
                                g_Removals[i][2], g_Removals[i][3], 0.25);
    }
    return 1;
}
```

4. Set the two distances on purpose. `streamdistance` decides when the server sends the object,
   `drawdistance` when the client renders it. A 300/300 pair pops in at the edge of the screen; 300/0
   inherits the stream distance and renders late on a fast flight.

5. Warm the area for teleports. `Streamer_UpdateEx` before moving the camera avoids the one-second empty
   room after `/enter`:

```pawn
Streamer_UpdateEx(playerid, 100.5, 200.25, 10.0);
SetPlayerPos(playerid, 100.5, 200.25, 10.0);
```

6. Count the objects at boot and refuse a mismatch, so a truncated export cannot ship silently:

```pawn
public OnGameModeInit()
{
    printf("[map] dynamic objects=%d expected=%d", CountDynamicObjects(), 4127);
    return 1;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| nothing past object 1000 exists | export still uses `CreateObject`, and the flat pool stops at 1000 | rewrite every line to `CreateDynamicObject` |
| buildings come back after a reconnect | removals were applied once at boot | replay `RemoveBuildingForPlayer` in `OnPlayerConnect` |
| textures white or missing | material index above 15, or the txd is not in `models/` | keep indices 0-15, ship the txd |
| objects appear only when you walk up | `drawdistance` far below `streamdistance` | match both, or leave `drawdistance` at 0 |
| count differs by a few objects | two exports appended, and each wrote `new g_Object[N]` | regenerate the header from the line count |
| a material landed on the wrong object | ids were renumbered by hand after conversion | convert ids and materials in the same pass |
| interior flickers at the edge of the room | custom shell and stock building occupy the same coordinates | remove the stock shell, then stream the custom one |

## Verification

```bash
python3 convert.py map.txt map.pwn
grep -c '= CreateDynamicObject(' map.pwn
grep -c 'SetDynamicObjectMaterial(' map.pwn
grep -c 'CreateObject(' map.pwn
```

Expected output for a 4127-object, 980-material export, with the last count at zero because nothing
should still use the flat pool:

```text
objects=4127 materials=980 unhandled=0
4127
980
0
```

Then confirm in game that the count the server reports equals the count in the file:

```bash
grep "\[map\] dynamic objects" server.log
```

## Sources (2026)

- https://github.com/Pottus/Texture-Studio
- https://github.com/fusez/Map-Editor-V3
- https://github.com/NexiusTailer/Ultimate-Creator
