---
name: progress-bar-hud-rendering
description: Use when a TextDraw progress bar drifts or flickers.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, hud, ui]
    category: samp
---

# Draw a progress bar with two boxes and no glyph sprites

A bar is two `useBox` textdraws: a background and a fill. Everything that goes wrong is a
coordinate problem. `TextDrawTextSize` takes the right and bottom **edges** on the 640x480 grid,
not a width and height delta, and the box is drawn from five units left and ten units above the
create coordinate.

## When to Use

- A bar's fill outgrows its background, or starts short of the left edge.
- The bar flickers once per second while a timer updates it.
- You need a health, armour, hunger, fuel or cast bar without a sprite sheet.
- One bar per player and the draws are being destroyed and re-created on every update.

## Compatibility & Stack Matrix (2026)

| Item | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | same API as 0.3.7 |
| Per-player draw | `CreatePlayerTextDraw(playerid, x, y, text)` | one pair per player, pool 256 |
| Box toggle | `PlayerTextDrawUseBox(td, true)` | without it `TextSize` only sets the click area |
| Size semantics | width = right edge, height = bottom edge | 640x480 grid, absolute coordinates |
| Box origin | `x - 5.0`, `y - 10.0` | documented offset from the create coordinate |
| Fill colour | `PlayerTextDrawBoxColor(playerid, td, 0xRRGGBBAA)` | alpha is the last byte |
| Text suppression | `PlayerTextDrawLetterSize(td, 0.0, 0.0)` | keeps the glyph out of the box |

Font 4 (sprite) and font 5 (model preview) are the exception: there `TextSize` really is width
and height. A bar must not use them — that is how bars end up needing a sprite per step.

## Production Implementation

1. Fix the geometry in one place. The two offsets exist so the box edges land where the create
   coordinate says:

```pawn
#include <openmp>

#define BAR_X        (320.0)   // create coordinate, same for both draws
#define BAR_Y        (400.0)
#define BAR_W        (120.0)   // visible width of the full bar
#define BAR_H        (8.0)     // visible height
#define BAR_EDGE_OFF (5.0)     // box starts 5.0 left of the create x
#define BAR_TOP_OFF  (10.0)    // box starts 10.0 above the create y

enum E_Bar { barBg, barFill }
new PlayerBar[MAX_PLAYERS][E_Bar];
new PlayerBarPct[MAX_PLAYERS];
```

2. Create both draws once, when the HUD is enabled. Background first so it paints under the
   fill; identical create coordinates give identical left and top edges:

```pawn
stock BarCreate(playerid)
{
    new Float:right  = BAR_X - BAR_EDGE_OFF + BAR_W;
    new Float:bottom = BAR_Y - BAR_TOP_OFF  + BAR_H;

    PlayerBar[playerid][barBg] = CreatePlayerTextDraw(playerid, BAR_X, BAR_Y, " ");
    PlayerTextDrawUseBox(playerid, PlayerBar[playerid][barBg], true);
    PlayerTextDrawBoxColor(playerid, PlayerBar[playerid][barBg], 0x00000099);
    PlayerTextDrawTextSize(playerid, PlayerBar[playerid][barBg], right, bottom);
    PlayerTextDrawLetterSize(playerid, PlayerBar[playerid][barBg], 0.0, 0.0);
    PlayerTextDrawSetOutline(playerid, PlayerBar[playerid][barBg], 0);

    PlayerBar[playerid][barFill] = CreatePlayerTextDraw(playerid, BAR_X, BAR_Y, " ");
    PlayerTextDrawUseBox(playerid, PlayerBar[playerid][barFill], true);
    PlayerTextDrawBoxColor(playerid, PlayerBar[playerid][barFill], 0x37C871FF);
    PlayerTextDrawTextSize(playerid, PlayerBar[playerid][barFill], right, bottom);
    PlayerTextDrawLetterSize(playerid, PlayerBar[playerid][barFill], 0.0, 0.0);
    PlayerTextDrawSetOutline(playerid, PlayerBar[playerid][barFill], 0);

    PlayerBarPct[playerid] = -1;                 // force the first BarSet to draw
}
```

3. Update the fill by right edge only. Percentage is clamped before the multiply, and an empty
   bar hides the fill instead of leaving a one-pixel sliver at the left edge:

```pawn
stock BarSet(playerid, pct)
{
    if (pct < 0)   pct = 0;
    if (pct > 100) pct = 100;
    if (pct == PlayerBarPct[playerid]) return 0;      // nothing changed, no packet

    PlayerBarPct[playerid] = pct;
    PlayerTextDrawTextSize(playerid, PlayerBar[playerid][barFill],
        BAR_X - BAR_EDGE_OFF + (BAR_W * float(pct) / 100.0),
        BAR_Y - BAR_TOP_OFF  + BAR_H);

    if (pct == 0) PlayerTextDrawHide(playerid, PlayerBar[playerid][barFill]);
    else          PlayerTextDrawShow(playerid, PlayerBar[playerid][barFill]);
    return 1;
}
```

4. Show the pair together, background then fill — showing only the fill leaves a floating strip
   until the next update. Feed it from state, not from a per-frame timer: a 1 Hz read that calls
   `BarSet` is enough, and `BarSet` already returns early when the value is unchanged:

```pawn
forward BarTick(playerid);
public BarTick(playerid)
{
    new Float:health;
    GetPlayerHealth(playerid, health);
    BarSet(playerid, floatround(health));            // 0..100 health onto a 0..100 bar
    return 1;
}
// where the HUD is enabled:
SetTimerEx("BarTick", 1000, true, "d", playerid);
```

5. Destroy on HUD disable or disconnect. Per-player draws leak against the 256 slot pool
   otherwise, and the next `CreatePlayerTextDraw` silently returns `INVALID_TEXT_DRAW`:
   `PlayerTextDrawDestroy` both ids, then set `PlayerBarPct` back to `-1`.

6. For a bar every client sees identically (a restart countdown), use `TextDrawCreate` and
   `TextDrawShowForAll` with the same edge maths. A two-tone fill is two more boxes with
   different `BoxColor` split at the same fractions — still arithmetic, still no sprite.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Fill grows past the background at 100% | width passed as a delta | pass the right edge: `BAR_X - 5.0 + BAR_W` |
| One-pixel line at 0% | zero-width box still painted | hide the fill when the clamped value is 0 |
| Flicker every second | draws destroyed and re-created on update | create once, call `PlayerTextDrawTextSize` |
| Bar height changes with the value | height tied to the percentage | height is constant: `BAR_Y - 10.0 + BAR_H` |
| HUD vanishes after ~10 minutes | per-player pool exhausted by re-creation | `PlayerTextDrawDestroy` on disable |

## Verification

The edge maths is cheap to test outside the game; the same formula runs in Python:

```bash
python3 - <<'PY'
X, Y, W, H = 320.0, 400.0, 120.0, 8.0
left, bottom = X - 5.0, Y - 10.0 + H
for pct in (0, 50, 100):
    print(pct, round(left + W * pct / 100.0, 1), round(bottom, 1))
PY
```

Expected — left edge constant at 315.0, right edge linear, bottom constant:

```text
0 315.0 398.0
50 375.0 398.0
100 435.0 398.0
```

## Sources (2026)

- https://open.mp/docs/scripting/functions/PlayerTextDrawTextSize — width/height are grid coordinates; the box starts 5.0 left and 10.0 above the create point; font 4/5 exception.
- https://open.mp/docs/scripting/functions/TextDrawUseBox — box rendering requires the `useBox` toggle.
- https://open.mp/docs/scripting/functions/TextDrawBoxColor — box colour and alpha semantics.
