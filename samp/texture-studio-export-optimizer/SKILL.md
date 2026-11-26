---
name: texture-studio-export-optimizer
description: Use when a Texture Studio export is bloated or slow.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, streamer, texturestudio]
    category: samp
---

# Export as streamer calls, dedupe the repeats, then chunk

Texture Studio writes one `CreateDynamicObject` per placed object and one
`SetDynamicObjectMaterial` per material slot — including the slots you re-set by accident while
texturing. A 3000-object interior therefore exports as 3000 creates plus up to 48000 material
lines, and the compile and the stream-in both pay for the duplicates.

## When to Use

- An export file is tens of thousands of lines and the gamemode compile time doubled.
- Start-up or interior entry stutters while objects stream in.
- The same wall was `mtset` five times and the export kept all five lines.
- You need one export split across files because a single function is too large to load.

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Editor | Texture Studio (Pottus / Crayder), filterscript | runs as its own local server, joined with the SA-MP client |
| Export command | `/exportmap` | name under 20 chars, then a draw-distance dialog |
| Export form | `CreateObject` / `CreateDynamicObjectEx` / `CreateDynamicObject` | pick the third and skip the rewrite pass |
| Output path | `scriptfiles/tstudio/ExportMaps/<name>.txt` | written by the filterscript, not by you |
| Material slots | 0-15 per object | slot 0 is often the whole surface |
| Draw distance | dialog value, `300.00` when empty or unparsable | stored per object in the last two arguments |

## Production Implementation

1. Build with `/newmap`, `/cobject`, `/mtset [slot] [texture]`, `/note` for hand-off comments.
   `/importmap` accepts existing `CreateObject` / `CreateDynamicObject` / `RemoveBuildingForPlayer`
   code if the map started life in another editor.

2. Export with `/exportmap`, name it, and enter a draw distance. The filterscript writes
   `scriptfiles/tstudio/ExportMaps/<name>.txt`; an empty or non-numeric distance becomes 300.

3. In the export dialog choose **CreateDynamicObject** (the third entry). The first entry writes
   `CreateObject` plus `SetObjectMaterial`, which you would then have to rewrite line by line.

4. Know exactly what the file contains before writing a tool for it: a header comment,
   `RemoveBuildingForPlayer` lines, `new tmpobjid;`, then each object with its materials, then
   the objects that have no materials at all:

```text
//Map Exported with Texture Studio By: [uL]Pottus
new tmpobjid;
tmpobjid = CreateDynamicObject(19325, 100.0, 200.0, 10.0, 0.0, 0.0, 0.0, -1, -1, -1, 300.00, 300.00); // wall
SetDynamicObjectMaterial(tmpobjid, 0, 19325, "mebb", "wall1", 0xFFFFFFFF);
```

5. Dedupe before the code is compiled. Objects are keyed on model and the six floats — the
   world, interior and distance arguments are deliberately ignored so an accidental re-place is
   caught. Materials are keyed per object and per slot, so the last `mtset` wins:

```python
import re, sys, pathlib
OBJ = re.compile(r"^\s*tmpobjid = CreateDynamicObject\((.+)\);\s*(?://.*)?$")
MAT = re.compile(r"^\s*SetDynamicObjectMaterial\(tmpobjid, (\d+), (.+)\);\s*$")
src, dst = sys.argv[1], sys.argv[2]
blocks, seen, cur = [], set(), None
for line in pathlib.Path(src).read_text().splitlines():
    o = OBJ.match(line)
    if o:
        field = tuple(x.strip() for x in o.group(1).split(",")[:7])
        cur = None if field in seen else [line.rstrip()]
        if cur: seen.add(field); blocks.append(cur)
        continue
    m = MAT.match(line)
    if m and cur is not None:
        key = (len(blocks) - 1, m.group(1), m.group(2).strip())
        if key not in seen: seen.add(key); cur.append(line.rstrip())
print(f"objects {len(blocks)} materials {sum(len(b) - 1 for b in blocks)}")
pathlib.Path(dst).write_text("new tmpobjid;\n" + "\n".join(l for b in blocks for l in b) + "\n")
```

6. Chunk the result. A Pawn function body has a size limit and a visible-item limit sits under
   it, so keep at most ~750 objects per file, include each chunk from one filterscript, and on a
   0.3.DL map raise the ceiling with `Streamer_SetVisibleItems(STREAMER_TYPE_OBJECT, 1500)`:

```pawn
// filterscripts/interior.pwn
#include <openmp>
#include <streamer>
#include "maps/interior_0.pwn"     // generated, 750 objects each
#include "maps/interior_1.pwn"
```

7. Keep the exported draw distance meaningful: 300 streams an interior across the whole block
   for every player in it. Set 150-200 for furniture and 300+ only for landmarks; the field is
   the last argument of each `CreateDynamicObject` and is safe to rewrite with one regex.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Compile dies with "too many statements" | one file with thousands of create calls | chunk to ~750 objects per file |
| Objects flicker at distance | draw distance shorter than the room | raise the per-object distance, not the stream radius |
| Texture appears on the wrong part | slot index reused for two materials | dedupe per slot, last write wins |
| Duplicate object in the map | the object was re-placed, export kept both | dedupe on model plus six floats |
| Nothing renders after loading | `#include <streamer>` missing in the chunk | include it once in each chunk file |
| Whole map vanishes on `gmx` | chunk filterscript unloaded without destroying objects | destroy with `DestroyDynamicObject` on exit |

## Verification

Run the dedupe pass (save the step-5 script as `ts_dedupe.py`) and read the counts — they must be
lower than the source, never higher:

```bash
python3 ts_dedupe.py scriptfiles/tstudio/ExportMaps/interior.txt interior.pwn
grep -c "CreateObject(" interior.pwn ; echo "static_exit=$?"
```

Expected for a small re-textured room exported twice, with one wall re-placed:

```text
objects 3 materials 2
0
static_exit=1
```

An object count that matches the source means nothing was duplicated; a material count higher
than 16 per object means a slot was written twice under different keys and the slot map is wrong.

## Sources (2026)

- https://github.com/Pottus/Texture-Studio — the filterscript source: `MapExport` writes `CreateDynamicObject(..., -1, -1, -1, dd, dd)` and one `SetDynamicObjectMaterial` per slot.
- https://github.com/Crayder/Texture-Studio/wiki/Using-Texture-Studio — `/newmap`, `/exportmap` into `Scriptfiles/tstudio/ExportMaps`, and the 2000-object client streaming limit.
- https://github.com/Pottus/Texture-Studio/blob/master/filterscripts/tstudio/tsmain.pwn — the export dialog order and the 300.0 default draw distance.
