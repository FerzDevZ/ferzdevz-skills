---
name: textdraw-radial-wheel-menu
description: Use when slices of a radial TextDraw menu miss.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui]
    category: samp
---

# Radial wheel: degrees on a 640x480 grid, one draw per slice

## When to Use

- A weapon or emote wheel highlights the slice next to the one the cursor is on.
- The wheel is centred on 16:9 but drifts off-centre on 4:3 or on the Android client.
- You need the slice index from a cursor position and the angles come out wrong.
- You are porting a wheel from a UI library that assumed radians.

## Compatibility & Stack Matrix (2026)

| Piece | Value | Consequence |
| --- | --- | --- |
| Canvas | 640x480 virtual grid stretched to the screen | one x unit is `W/640` px, one y unit `H/480` px |
| y axis | grows downward | a positive angle from `floatsin` points *down*, not up |
| `floatsin` / `floatcos` | take **degrees** | no `PI/180` conversion before calling them |
| `atan2(y, x)` | takes y first, returns **degrees** in [-180, 180] | no `180/PI` conversion after calling it |
| Click callback | `OnPlayerClickTextDraw(playerid, Text:clickedid)` | an id only, never coordinates |
| Alignment | `TEXT_DRAW_ALIGN_CENTRE` | create position is the centre, TextSize is width x height |

## Production Implementation

1. Put the geometry in one place, so a radius change cannot desynchronise the labels from the boxes:

```pawn
#define WHEEL_CX 320.0
#define WHEEL_CY 240.0
#define WHEEL_R  90.0
#define WHEEL_SLICES 8
#define WHEEL_START -90.0        // first slice points up

stock Float:WheelX(Float:angle, Float:radius) { return WHEEL_CX + radius * floatcos(angle); }
stock Float:WheelY(Float:angle, Float:radius) { return WHEEL_CY + radius * floatsin(angle); }
stock Float:WheelStep() { return 360.0 / float(WHEEL_SLICES); }
stock Float:WheelMid(slice) { return WHEEL_START + (float(slice) + 0.5) * WheelStep(); }
stock Float:WheelChord(Float:radius) { return 2.0 * radius * floatsin(WheelStep() / 2.0); }
```

2. Size each label from the chord it fits inside: `2 * r * sin(step/2)`, or it overlaps its neighbour.

3. Create one TextDraw per slice, centred on its mid-angle, and let the TextSize be the hitbox. Centred
   alignment makes the create position the centre of the box and TextSize a width x height pair:

```pawn
new Text:g_Wheel[WHEEL_SLICES];
new g_WheelLabel[WHEEL_SLICES][16];

stock BuildWheel()
{
    new Float:w = WheelChord(WHEEL_R) - 6.0;   // 6 units of gutter
    for (new i = 0; i < WHEEL_SLICES; i++)
    {
        new Float:mid = WheelMid(i);
        g_Wheel[i] = TextDrawCreate(WheelX(mid, WHEEL_R), WheelY(mid, WHEEL_R), " ");
        TextDrawAlignment(g_Wheel[i], TEXT_DRAW_ALIGN_CENTRE);
        TextDrawTextSize(g_Wheel[i], w, 18.0);
        TextDrawUseBox(g_Wheel[i], true);
        TextDrawBoxColor(g_Wheel[i], 0x00000099);
        TextDrawColor(g_Wheel[i], 0xFFFFFFFF);
        TextDrawSetSelectable(g_Wheel[i], true);
    }
    return 1;
}
```

4. Show, then capture the cursor: `TextDrawSetSelectable` only reacts once the draw is visible.

```pawn
stock ShowWheel(playerid)
{
    for (new i = 0; i < WHEEL_SLICES; i++)
    {
        TextDrawSetString(g_Wheel[i], g_WheelLabel[i]);
        TextDrawShowForPlayer(playerid, g_Wheel[i]);
    }
    SelectTextDraw(playerid, 0xFFFFFF44);        // cursor + hover colour
    return 1;
}

stock HideWheel(playerid)
{
    CancelSelectTextDraw(playerid);
    for (new i = 0; i < WHEEL_SLICES; i++) TextDrawHideForPlayer(playerid, g_Wheel[i]);
    return 1;
}
```

5. Map the click by id. The callback carries no coordinates, so the slice index is the loop comparing the
   clicked handle against the array; do not try to recover an angle from it:

```pawn
public OnPlayerClickTextDraw(playerid, Text:clickedid)
{
    if (clickedid == Text:INVALID_TEXT_DRAW) return HideWheel(playerid);   // Escape / right click
    for (new i = 0; i < WHEEL_SLICES; i++)
        if (clickedid == g_Wheel[i]) return WheelPick(playerid, i);
    return 0;
}
```

6. When you *do* have a cursor position (camera aim, map sight, joystick), get the slice from the vector.
   `atan2` already returns degrees, so only the offset and the wrap are left:

```pawn
stock WheelSliceAt(Float:px, Float:py)
{
    new Float:ang = atan2(py - WHEEL_CY, px - WHEEL_CX);      // degrees, [-180, 180]
    if (ang < WHEEL_START) ang += 360.0;
    new slice = floatround((ang - WHEEL_START) / WheelStep(), floatround_floor);
    return slice % WHEEL_SLICES;
}
```

7. On non-4:3 clients the wheel is an ellipse: `WHEEL_R` is virtual units. Scale per axis, or accept it.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Highlight is one slice off near the top | `WHEEL_START` not subtracted before dividing | `(ang - WHEEL_START)` then `% WHEEL_SLICES` |
| Slices land at 45 degrees on a 4-slice wheel | `atan2` result multiplied by 57.3 | open.mp returns degrees, drop the conversion |
| Every label mirrored vertically | positive `floatsin` treated as "up" on a y-down grid | negate y, or start at `-90` as above |
| Adjacent labels overlap at the inner edge | width taken from the full radius | width from `WheelChord`, plus a 6-unit gutter |
| Nothing is clickable | `TextDrawSetSelectable` on a draw never shown | show first, then `SelectTextDraw` |
| Wheel stays after Escape | `INVALID_TEXT_DRAW` branch missing | `CancelSelectTextDraw` + hide there |

## Verification

```bash
pawncc gamemodes/main.pwn -d3 -ogamemodes/main.amx && grep -E "WHEEL" server/log.txt
python3 -c "import math;print([(i,round(320+90*math.cos(math.radians(-90+45*i)),1),round(240+90*math.sin(math.radians(-90+45*i)),1)) for i in range(8)])"
```

Expected with `WHEEL_R 90`, centre `(320,240)` and 8 slices: the compiler prints no `Error:` lines and
the log shows eight calls, 45 degrees apart, the first straight up:

```text
WHEEL slice=0 angle=-90.0 x=320.0 y=150.0 chord=68.9
WHEEL slice=1 angle=-45.0 x=383.6 y=176.4 chord=68.9
WHEEL slice=2 angle=0.0 x=410.0 y=240.0 chord=68.9
WHEEL slice=3 angle=45.0 x=383.6 y=303.6 chord=68.9
WHEEL slice=4 angle=90.0 x=320.0 y=330.0 chord=68.9
WHEEL slice=5 angle=135.0 x=256.4 y=303.6 chord=68.9
WHEEL slice=6 angle=180.0 x=230.0 y=240.0 chord=68.9
WHEEL slice=7 angle=225.0 x=256.4 y=176.4 chord=68.9
```

The `python3 -c` line must reproduce those eight points to one decimal.

- Manual: `WheelSliceAt(320.0, 150.0)` returns 0 (straight up), `WheelSliceAt(410.0, 240.0)` returns 2
  (right), and `(320.0, 149.9)` must still return 0 rather than wrapping to 7.

## Sources (2026)

- https://open.mp/docs/scripting/functions/atan2 — y-first arguments, result in degrees, [-180, 180].
- https://open.mp/docs/scripting/functions/TextDrawAlignment — `TEXT_DRAW_ALIGN_CENTRE` swaps the
  meaning of the TextSize pair to width x height.
- https://open.mp/docs/scripting/callbacks/OnPlayerClickTextDraw — the callback carries the draw id and
  nothing else.
