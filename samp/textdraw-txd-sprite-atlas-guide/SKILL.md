---
name: textdraw-txd-sprite-atlas-guide
description: Use when HUD icons come from TXD sprites, not models.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# TXD sprites as a UI atlas

## When to Use

- The HUD needs icons (money, waypoint, weapon, status) without shipping custom models.
- A sprite renders as nothing, and the server log says nothing about it.
- An icon is stretched, cropped or offset relative to its box.
- A clickable sprite ignores clicks until you find the right order of calls.
- You are about to copy a "15 sprites per texture" limit from a forum post and want the documented
  numbers instead.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Font id | `TEXT_DRAW_FONT_SPRITE_DRAW` (4) | font 5 is a model preview, not a sprite |
| Font id range | `> 5` does not display, `> 16` crashes the client | documented on `TextDrawFont` |
| Sprite reference | `"library:texture"` | `.txd` is not appended, and the case must match the library listing |
| Usable libraries | shipped TXDs such as `hud`, `samp`, `LD_BEAT`, `LOADSCS` | the client must actually have the TXD loaded |
| Size | `TextDrawTextSize` | for font 4/5 the two values are **width and height**, not corner coordinates |
| Box origin | 10.0 units up and 5.0 left of `TextDrawCreate` | matters when a box backs a sprite |
| Sprites on screen | 100 per client | documented limit; more are dropped |
| Textdraw pool | 2048 global / 256 per player | one cached `Text:` per icon, never per frame |

The open.mp sprite list and limits pages do not document a per-texture sprite cap. The numbers that do
bite are 100 sprites on one client's screen, a 1024-character textdraw string, and the pool sizes
above — design against those, and measure before believing any other figure.

## Production Implementation

1. Pick names from the documented list rather than guessing. These are real `hud.txd` textures, note the
   mixed case in the library listing:

```text
hud:radar_cash
hud:radar_waypoint
hud:radar_saveGame
hud:radar_qmark
hud:fist
```

2. Declare an enum of icons and cache one global `Text:` per icon. Recreating a textdraw per frame burns
   pool slots and flickers:

```pawn
enum
{
    ICON_CASH,
    ICON_WAYPOINT,
    ICON_SAVE,
    ICON_COUNT
}

new const gIconSprite[ICON_COUNT][] =
{
    "hud:radar_cash",
    "hud:radar_waypoint",
    "hud:radar_saveGame"
};

new Text:gIcon[ICON_COUNT];
```

3. Create with font 4 and set the size as width/height. This is the single most common source of a
   stretched sprite: the values are not corners:

```pawn
stock CreateIcon(idx, Float:x, Float:y, Float:size)
{
    gIcon[idx] = TextDrawCreate(x, y, gIconSprite[idx]);
    TextDrawFont(gIcon[idx], TEXT_DRAW_FONT_SPRITE_DRAW);
    TextDrawTextSize(gIcon[idx], size, size);   // width, height for sprite fonts
    TextDrawSetOutline(gIcon[idx], 0);
    TextDrawSetShadow(gIcon[idx], 0);
    TextDrawSetProportional(gIcon[idx], false);
    return 1;
}
```

4. Make a sprite clickable only after its area exists. `TextDrawTextSize` defines the clickable area
   whether or not `TextDrawUseBox` is on, and `SelectTextDraw` is what routes the click to you:

```pawn
stock MakeIconClickable(playerid, idx)
{
    TextDrawSetSelectable(gIcon[idx], true);
    SelectTextDraw(playerid, 0xFFFFFFFF);
    return 1;
}
```

Handle the click in `OnPlayerClickTextDraw`, then `CancelSelectTextDraw` when the UI closes.

5. Put a sprite in a panel by treating the panel as a box and the sprite as an overlay. Because a box
   starts 10.0 units up and 5.0 left of its create coordinate, offset the sprite by the same amount or
   it will sit off-centre:

```pawn
TextDrawCreate(320.0, 220.0, "hud:radar_cash");   // sprite
// the box for the same visual origin starts at 315.0, 210.0
```

6. Change text freely, but re-show after a font change. The string updates live; a font change on an
   already-visible textdraw may need another show call on the client:

```pawn
TextDrawSetString(gIcon[ICON_CASH], "hud:radar_qmark");
TextDrawShowForAll(gIcon[ICON_CASH]);
```

7. Scale-check on two resolutions. The grid is 640x480 and scales, so an icon tuned on 1280x720 will be
   blurry on 1920x1080 if the source texture is small; author the TXD at the size you display.

8. Custom TXDs are only usable where the client has them loaded. On a stock client that means the
   libraries shipped with the game; anything else has to be distributed to the client and referenced by
   the library name without the `.txd` extension.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Sprite never appears, no log line | wrong library, wrong texture name or the wrong case | copy the `library:texture` pair from the sprite list |
| Sprite appears but is stretched or cropped | `TextDrawTextSize` used as corner coordinates | pass width and height for font 4 |
| Whole textdraw invisible | font id above 5 | use 4 for sprites, 5 for model previews |
| Client crashes when the HUD shows | font id above 16 | clamp the font value, rebuild the textdraw |
| Click does nothing | selectable set but no area, or no `SelectTextDraw` | set `TextDrawTextSize` first, then select |
| Some icons blank for one player only | custom TXD not installed on that client | fall back to a shipped sprite, or ship the TXD |
| Icons stop appearing after a HUD rewrite | more than 100 sprites on screen | merge icons into fewer textdraws, drop the rest |

## Verification

```bash
pawncc -i./includes -d3 -ogamemodes/main.amx gamemodes/main.pwn && echo "compiled"
grep -rhoE '"[a-zA-Z0-9_]+:[a-zA-Z0-9_]+"' gamemodes/main.pwn | sort -u
grep -c 'TextDrawCreate' gamemodes/main.pwn
```

Expected output — the compile passes, only documented sprite ids are referenced, and the icon count
stays well inside the 2048 slot pool:

```text
compiled
"hud:radar_cash"
"hud:radar_saveGame"
"hud:radar_waypoint"
3
```

The render itself has to be confirmed on a client: show the HUD at 1280x720 and 1920x1080 and check that
each icon keeps its aspect ratio and that 100-sprites-on-screen is not exceeded.

## Sources (2026)

- https://open.mp/docs/scripting/resources/textdrawsprites
- https://open.mp/docs/scripting/functions/TextDrawFont
- https://open.mp/docs/scripting/functions/TextDrawTextSize
