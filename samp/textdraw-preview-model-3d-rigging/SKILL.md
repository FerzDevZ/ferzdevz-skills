---
name: textdraw-preview-model-3d-rigging
description: Use when TextDraw 3D model previews render wrong.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui]
    category: samp
---

# Render and rotate 3D model previews in TextDraws

A preview is a TextDraw with one special font, a model id, and a camera described by three
rotation angles plus a zoom. Miss the font and the box is invisible; pass a model id the client
does not know and you get the yellow-and-black question mark.

## When to Use

- You need a rotating skin or vehicle preview in a shop, auction or spawn menu.
- An existing preview is blank, a question mark, or the wrong size, and each player needs their own angle.

## Compatibility & Stack Matrix (2026)

| Function | Signature | Requirement |
| --- | --- | --- |
| `TextDrawFont` | `(Text:text, font)` | must be `TEXT_DRAW_FONT_MODEL_PREVIEW` |
| `TextDrawSetPreviewModel` | `(Text:text, model)` | GTA SA or SA-MP model id |
| `TextDrawSetPreviewRot` | `(Text:text, Float:rx, Float:ry, Float:rz, Float:zoom)` | model must already be set |
| `TextDrawSetPreviewVehCol` | `(Text:text, colour1, colour2)` | vehicle models only |
| `TextDrawTextSize` | `(Text:text, Float:x, Float:y)` | box width and height, not screen position |
| `PlayerTextDrawSetPreviewModel` | `(playerid, PlayerText:text, model)` | per-player copy |
| `PlayerTextDrawSetPreviewRot` | `(playerid, PlayerText:text, Float:rx, Float:ry, Float:rz, Float:zoom)` | per-player angle |
| `PlayerTextDrawSetPreviewVehCol` | `(playerid, PlayerText:text, colour1, colour2)` | per-player colours |

Docs note on zoom: default `1.0`, smaller values move the camera closer and larger values further
away. Every function above is a no-op unless the font is the model preview font.

## Production Implementation

1. Create the draw, set the font first, then the box, then the model. Track existence in a bool:
   there is no valid "empty" handle to compare a destroyed draw against.

```pawn
new PlayerText:g_Preview[MAX_PLAYERS];
new g_PreviewModel[MAX_PLAYERS];
new g_PreviewAngle[MAX_PLAYERS];
new g_PreviewTimer[MAX_PLAYERS];
new bool:g_PreviewActive[MAX_PLAYERS];
```

2. Build one player draw per viewer. A global `TextDraw` shares rotation and colours with the
   whole server, so a global preview can only ever show one angle to everyone.

```pawn
stock Preview_Create(playerid, model)
{
    g_Preview[playerid] = CreatePlayerTextDraw(playerid, 320.0, 240.0, "_");
    PlayerTextDrawFont(playerid, g_Preview[playerid], TEXT_DRAW_FONT_MODEL_PREVIEW);
    PlayerTextDrawUseBox(playerid, g_Preview[playerid], true);
    PlayerTextDrawBoxColor(playerid, g_Preview[playerid], 0x000000FF);
    PlayerTextDrawBackgroundColor(playerid, g_Preview[playerid], 0x000000FF);
    PlayerTextDrawTextSize(playerid, g_Preview[playerid], 90.0, 110.0);
    PlayerTextDrawSetPreviewModel(playerid, g_Preview[playerid], model);
    PlayerTextDrawSetPreviewRot(playerid, g_Preview[playerid], -10.0, 0.0, 0.0, 1.0);

    g_PreviewModel[playerid] = model, g_PreviewAngle[playerid] = 0, g_PreviewActive[playerid] = true;
    PlayerTextDrawShow(playerid, g_Preview[playerid]);
}
```

3. Colour a vehicle preview after the model is set, and only for vehicle ids. Skin ids and
   object ids ignore both colour parameters.

```pawn
stock Preview_SetVehicleColours(playerid, colour1, colour2)
{
    if (g_PreviewModel[playerid] < 400 || g_PreviewModel[playerid] > 611) return 0;
    PlayerTextDrawSetPreviewVehCol(playerid, g_Preview[playerid], colour1, colour2);
    return 1;
}
```
4. Spin on a timer, not per frame, and update the rotation in place. Recreating the draw each
   step is what produces the one-frame blank players read as flicker.

```pawn
#define PREVIEW_TICK (100)   // 10 updates per second is smooth for a menu

stock Preview_Start(playerid)
{
    g_PreviewTimer[playerid] = SetTimerEx("Preview_Tick", PREVIEW_TICK, true, "d", playerid);
    return 1;
}

forward Preview_Tick(playerid);
public Preview_Tick(playerid)
{
    if (!IsPlayerConnected(playerid) || !g_PreviewActive[playerid]) return 0;

    g_PreviewAngle[playerid] = (g_PreviewAngle[playerid] + 8) % 360;
    PlayerTextDrawSetPreviewRot(playerid, g_Preview[playerid],
        -10.0, 0.0, float(g_PreviewAngle[playerid]), 1.0);
    return 1;
}
```

5. Destroy on close: stop the timer, hide, destroy, clear the flag, in that order.

```pawn
stock Preview_Destroy(playerid)
{
    if (!g_PreviewActive[playerid]) return 0;
    if (g_PreviewTimer[playerid]) KillTimer(g_PreviewTimer[playerid]);
    g_PreviewTimer[playerid] = 0;
    PlayerTextDrawHide(playerid, g_Preview[playerid]);
    PlayerTextDrawDestroy(playerid, g_Preview[playerid]);
    g_PreviewActive[playerid] = false;
    g_PreviewModel[playerid] = 0;
    return 1;
}
```

6. Sanity-check the id before calling: `1` is CJ, `411` is the Infernus, and object ids such as
   `18646` work too. An id outside the client's model set is accepted by the server and drawn as
   a question mark, so the bug looks like a UI fault rather than an error.

## Failure Modes & Fixes
| Symptom | Cause | Fix |
| --- | --- | --- |
| Yellow and black question mark | model id not present in the client | validate the id against models you ship |
| Empty box, no model at all | font is not `TEXT_DRAW_FONT_MODEL_PREVIEW` | call `PlayerTextDrawFont` before the model |
| Preview is a sliver or covers the screen | `TextDrawTextSize` values used as coordinates | pass box width and height, not X/Y position |
| Rotation ignored | `SetPreviewRot` called before a model was set | set the model first, then the rotation |
| Vehicle colours do nothing | model is a skin or object | apply colours only for 400-611 |
| Every player sees the same angle | global `TextDraw` used | switch to a `PlayerTextDraw` per viewer |
| Preview blinks once per update | draw destroyed and recreated per step | update the rotation on the existing draw |

## Verification

Compile, then confirm the preview calls exist on the player path:

```bash
grep -c "SetPreviewModel\|SetPreviewRot\|SetPreviewVehCol" gamemodes/preview.pwn
sampctl build 2>&1 | tail -2
```

```text
4
Build complete; written to gamemodes/preview.amx
```

Open the menu with a launcher client and read the created handle plus model id:

```bash
grep "PREVIEW td=" log.txt | tail -1
```

```text
PREVIEW td=0 model=411
```

`model=411` on the same line as a handle means the draw exists and the model reached the client.
In game the Infernus must complete a full turn in about four and a half seconds with no blank
frame; a static model with an advancing angle in the log means the draw was never shown.

## Sources (2026)

- https://open.mp/docs/scripting/functions/TextDrawSetPreviewModel
- https://open.mp/docs/scripting/functions/TextDrawSetPreviewRot
- https://open.mp/docs/scripting/functions/PlayerTextDrawSetPreviewModel
