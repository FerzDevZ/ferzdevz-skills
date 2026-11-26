---
name: dynamic-object-material-text-signs
description: Use when a sign must be painted onto a 3D object.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, streamer, materials]
    category: samp
---

# Material text signs that survive streaming

## When to Use

- A building needs a readable sign and a custom TXD is not worth shipping.
- The sign looks right in the editor but is blank on the live server.
- Text must change at runtime: dock numbers, player counts, prices.
- You are about to scatter `SetDynamicObjectMaterialText` calls through a loader and want one table.
- Not for HUD text; that is `global-vs-player-td-budget`.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| Native | `SetDynamicObjectMaterialText` (streamer 2.9.6) | plugin native; no core equivalent for dynamic objects |
| Signature | `(objectid, materialindex, const text[], materialsize, const fontface[], fontsize, bold, fontcolor, backcolor, textalignment)` | defaults `256x128`, `"Arial"`, `24`, bold `1`, white, `0` |
| Slots | `0` to `15` | one material per slot: text and texture cannot share an index |
| Text length | 2048 characters | longer strings are dropped by the client, no error |
| Sizes | `OBJECT_MATERIAL_SIZE_32x32` (10) to `_512x512` (130) | steps of 10, 13 values in the enum |
| Colour | ARGB integer | `0xFFFFFFFF` white, `0x00000000` no background box |
| Alignment | `0` left, `1` centre, `2` right | the enum tag does not match the native parameter |

## Production Implementation

1. Reserve one slot for text across the whole map, and use short alignment names. The include's
   `OBJECT_MATERIAL_TEXT_ALIGN_CENTRE` is longer than the compiler's 31-character symbol limit:

```pawn
#define SIGN_TEXT_MAX    (2048)     // documented client limit
#define SIGN_SLOT        (3)        // 0..15, reserved for text on every sign object

#define SIGN_ALIGN_LEFT   (OBJECT_MATERIAL_TEXT_ALIGN:0)
#define SIGN_ALIGN_CENTRE (OBJECT_MATERIAL_TEXT_ALIGN:1)
#define SIGN_ALIGN_RIGHT  (OBJECT_MATERIAL_TEXT_ALIGN:2)
```

2. Keep the signs in a row table, not in the loader, so a new sign is one line and the set can be
   rebuilt from data:

```pawn
enum E_Sign
{
    signModel,
    Float:signX,
    Float:signY,
    Float:signZ,
    Float:signRot,
    signText[64],
    signSize,
    signFont[24],
    signFontSize,
    signColour,
    signBack,
    OBJECT_MATERIAL_TEXT_ALIGN:signAlign
};

static const gSigns[][E_Sign] =
{
    { 19483, 1685.0, -2240.0, 13.6, 90.0, "DOCK 4", OBJECT_MATERIAL_SIZE_256x128,
      "Arial", 24, 0xFFFFFFFF, 0x00000000, SIGN_ALIGN_CENTRE },
    { 19483, 1685.0, -2250.0, 13.6, 90.0, "BERTHS 1-8", OBJECT_MATERIAL_SIZE_512x128,
      "Arial", 32, 0xFFFFDD00, 0x00000000, SIGN_ALIGN_LEFT }
};
```

3. Create and paint in one pass. The plugin stores the material and re-sends it on stream-in, so a
   single call at creation is enough; paint before the object exists and there is nothing to paint:

```pawn
stock Sign_Build(row, world = -1)
{
    new objectid = CreateDynamicObject(gSigns[row][signModel], gSigns[row][signX], gSigns[row][signY],
                                       gSigns[row][signZ], 0.0, 0.0, gSigns[row][signRot], world);
    if (!IsValidDynamicObject(objectid)) return INVALID_STREAMER_ID;

    SetDynamicObjectMaterialText(objectid, SIGN_SLOT, gSigns[row][signText], gSigns[row][signSize],
                                 gSigns[row][signFont], gSigns[row][signFontSize], 1,
                                 gSigns[row][signColour], gSigns[row][signBack],
                                 _:gSigns[row][signAlign]);
    printf("sign row=%d obj=%d slot=%d len=%d", row, objectid, SIGN_SLOT, strlen(gSigns[row][signText]));
    return objectid;
}
```

4. Guard the length before calling. The client truncates silently, so an over-long string reads as a
   layout bug instead of a limit:

```pawn
stock Sign_SetText(objectid, const text[])
{
    if (strlen(text) > SIGN_TEXT_MAX) return 0;
    SetDynamicObjectMaterialText(objectid, SIGN_SLOT, text, OBJECT_MATERIAL_SIZE_256x128,
                                 "Arial", 24, 1, 0xFFFFFFFF, 0x00000000,
                                 _:SIGN_ALIGN_CENTRE);
    return 1;
}
```

5. Pick the size by looking, not by guessing: the canvas is stretched over the object's UV, so a
   `512x128` texture on a narrow panel shrinks the glyphs. Spawn one object per candidate size in a
   test world, pick the winner, then write it into the table.

6. Keep each sign single-line. Multi-line layout is several objects or several slots; a wrapped
   string spends the 2048-character budget and loses the alignment you chose.

7. Apply in the same pass as the object, and log the slot plus length. A blank sign is then traceable
   to a call rather than to the client's font handling.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Sign blank, object correctly textured | a retexture call wrote the same slot afterwards | give text its own index, e.g. `3`, retextures on `0..2` |
| `warning 200: symbol "OBJECT_MATERIAL_TEXT_ALIGN_CENT" is truncated to 31 characters` | the include's enum name is over the symbol limit | define `SIGN_ALIGN_CENTRE` and use that in the table |
| `warning 213: expected tag none, found OBJECT_MATERIAL_TEXT_ALIGN` | the native takes an untagged `textalignment` | `_:` cast at the call site |
| Text cut mid-word | string over 2048 characters | reject with `strlen` before the call |
| Glyphs tiny on a large wall | `256x128` stretched over a big UV | raise `materialsize` or split the sign into panels |
| Sign invisible for some players only | object created in another world or interior | pass the real `worldid`, not `-1` by accident |
| Dark rectangle hides the text | `backcolor` alpha near `0xFF` | `0x00000000` for no box, or alpha below `0x80` |

## Verification

```bash
pawncc -i"$HOME/samp-sdk/omp-stdlib" \
       -i"$HOME/.config/sampctl/packages/github.com/samp-incognito/samp-streamer-plugin/default" \
       -d3 '-;+' '-(+' -oprobe_sign.amx probe_sign.pwn; echo "exit=$?"
```

Expected for the code above - no tag warning, no truncation warning, exit `0`:

```text
Pawn compiler 3.10.10	 	 	 	Copyright (c) 1997-2006, ITB CompuPhase

Header size:            400 bytes
Code size:             1576 bytes
Data size:              940 bytes
Stack/heap size:      16384 bytes; estimated max. usage=73 cells (292 bytes)
Total requirements:   19300 bytes
exit=0
```

A `warning 200` here means the long enum name crept back into the table; a `warning 213` means a
missing `_:` cast. Both are build failures under `-E` in CI.

## Sources (2026)

- https://github.com/samp-incognito/samp-streamer-plugin
- https://open.mp/docs/scripting/functions/SetObjectMaterialText
- https://open.mp/docs/scripting/resources/limits
