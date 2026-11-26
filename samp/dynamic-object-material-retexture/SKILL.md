---
name: dynamic-object-material-retexture
description: Use when objects need new textures without custom models.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping, materials]
    category: samp
---

# Retexture streamed objects through material slots

## When to Use

- A wall, floor or sign needs a different texture and a new model is not an option.
- A map editor preview shows the right texture but the live server shows the stock one.
- You need one material change on hundreds of objects, and per-object model copies would blow the budget.
- Not for text on a surface; that is `SetDynamicObjectMaterialText` on its own slot, covered below.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Notes |
| --- | --- | --- |
| open.mp server | 1.6.7.3218 | `SetObjectMaterial` exists for core objects only |
| dynamic objects | streamer 2.9.6 | `SetDynamicObjectMaterial` is a streamer native, not a core one |
| material slots | 0 to 15 per object | indices outside that range are accepted by the plugin and ignored by the client |
| colour format | ARGB integer | `0` keeps the existing material colour |
| special model ids | `0` = alpha, `-1` = colour only | with `-1`, pass `"none"` for txd and texture name |
| custom TXD delivery | open.mp artwork (`artwork.enable`, `artwork.models_path`) | a TXD the client does not have renders as nothing |
| material text | 2048 characters max | longer strings are truncated by the client |

The plugin stores materials per slot in a map and re-sends them when the object streams in, so applying at creation time is enough. Calling `SetDynamicObjectMaterial` on a slot also clears any material text on that same slot, and the reverse is true: one slot holds one kind of material.

## Production Implementation

1. Decide the slot map before writing code: slot 0 for the main face, 1 for trim, 2 for colour-only tinting, 3 reserved for text. Never let a text routine and a texture routine share an index.

2. Keep the retexture rows in data, next to the objects they belong to, not inline at each `CreateDynamicObject`:

```pawn
enum E_Retex
{
    rtSlot,
    rtModel,
    rtTxd[32],
    rtTexture[32],
    rtColour
};

static const gDockWall[][E_Retex] =
{
    { 0, 19483, "dock_txd", "wall_brick", 0xFFFFFFFF },
    { 1, 19483, "dock_txd", "wall_trim",  0xFF303030 }
};

stock ApplyRetex(objectid, const rows[][E_Retex], count)
{
    for (new i = 0; i < count; i++)
    {
        if (rows[i][rtSlot] < 0 || rows[i][rtSlot] > 15) continue;   // client renders 0..15 only

        SetDynamicObjectMaterial(objectid, rows[i][rtSlot], rows[i][rtModel],
                                 rows[i][rtTxd], rows[i][rtTexture], rows[i][rtColour]);
    }
    return 1;
}
```

3. Apply immediately after creation, in the same loader pass, so the material is part of the object before any player streams it in:

```pawn
new objectid = CreateDynamicObject(19483, 1685.0, -2240.0, 13.5, 0.0, 0.0, 0.0, WORLD_LS, INTERIOR_NONE, -1, 200.0, 200.0);
ApplyRetex(objectid, gDockWall, sizeof gDockWall);
```

4. Tint without changing the texture: model id `-1` with `"none"` for both names. This is the only way to recolour a stock texture without pointing at another model, and it costs the object its vertex lighting.

```pawn
SetDynamicObjectMaterial(objectid, 2, -1, "none", "none", 0xFF204080);
```

5. Text lives on its own slot and survives restarts only if the same call runs again. Use a short local constant for alignment: the stock `OBJECT_MATERIAL_TEXT_ALIGN_CENTER` name is truncated to 31 characters and warns on every build.

```pawn
#define TEXT_ALIGN_CENTRE (1)

SetDynamicObjectMaterialText(objectid, 3, "DOCK 4", OBJECT_MATERIAL_SIZE_256x128,
                             "Arial", 32, 1, 0xFFFFFFFF, 0xFF000000, TEXT_ALIGN_CENTRE);
```

6. Ship the TXD. With open.mp artwork the client pulls it from `artwork.models_path`; without an artwork entry the material compiles, loads, and renders as nothing on a clean client. Verify with a client that has never seen the server before, not with the map editor.

7. Check the applied state from the server instead of eyeballing it. `IsDynamicObjectMaterialUsed` and `GetDynamicObjectMaterial` are include-only natives:

```pawn
printf("[retex] object %d slot 0 used=%d", objectid, IsDynamicObjectMaterialUsed(objectid, 0));
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| object is untextured or see-through in game | TXD not present on the client | ship it via open.mp artwork, or use stock txd names |
| colour applies but lighting goes flat | model id -1 replaces the material colour and drops vertex lighting | accept it, or bake the tint into the texture |
| label disappears when a texture is set | material and text share one slot; the last call wins | give text its own index |
| slot 16 and above do nothing | the client only renders slots 0-15 | clamp the slot in the apply loop |
| retexture gone after a restart | applied by hand in a session, not in the loader | apply from the data rows during load |
| `SetObjectMaterial` on a dynamic id retextures the wrong object | dynamic ids are plugin handles, not client object ids | use `SetDynamicObjectMaterial` |
| editor shows the texture, server does not | editor reads local TXDs the clients never download | test on a clean client install |

## Verification

Compile, then prove the data is inside the slot range:

```bash
awk '$1 < 0 || $1 > 15 {print "bad slot", $1}' maps/retex.cfg; echo "slots ok"
```

Expected: no `bad slot` lines, then `slots ok`. In game, `/retexinfo <objectid>` should print `slot 0 used=1` for every entry in the table, and a client with no local map files must still show the texture. Final compile:

```bash
pawncc -i./includes -d3 -O1 -;+ -(+ -ogamemodes/main.amx gamemodes/main.pwn 2>&1 | tail -2
```

Expected: `0 Errors` and `0 Warnings`.

## Sources (2026)

- [open.mp SetObjectMaterial](https://open.mp/docs/scripting/functions/SetObjectMaterial) — slot range 0-15, ARGB, model id 0/-1 semantics, `"none"` names, vertex-lighting note.
- [streamer.inc 2.9.6](https://raw.githubusercontent.com/samp-incognito/samp-streamer-plugin/master/streamer.inc) — `SetDynamicObjectMaterial`/`SetDynamicObjectMaterialText` signatures and defaults.
- [open.mp config.json](https://open.mp/docs/server/config.json) — `artwork.enable`, `artwork.models_path`, `artwork.cdn` for TXD delivery.
