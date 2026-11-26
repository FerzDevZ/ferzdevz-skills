---
name: textdraw-widescreen-mobile-scaling
description: Use when a HUD clips on ultrawide or phone screens.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui, mobile]
    category: samp
---

# TextDraw scaling across aspect ratios and phones

## When to Use

- A HUD that is correct at 16:9 is clipped at 21:9 or sits under a notch on a phone.
- Buttons drawn as squares look wider than tall on a widescreen display.
- A panel built once at connect has the wrong geometry after the player changes display settings.
- You are adding a mobile or launcher client and the server cannot see its real resolution.

## Compatibility & Stack Matrix (2026)

| Fact | Value | Consequence |
| --- | --- | --- |
| Canvas | 640x480 grid stretched over the whole screen | coordinates are percentages of the screen, not pixels |
| Reported aspect | 1.3333334 (4:3), 1.2470589 (5:4 letterbox), 1.7764707 (16:9) | `GetPlayerCameraAspectRatio` only ever returns these three |
| What it measures | the game's widescreen display option | a 21:9 monitor still reports 16:9, so design for the extremes |
| Unit size | x unit = `W/640` px, y unit = `H/480` px | at 16:9 one x unit is 1.33x wider than one y unit |
| Square cell | `h = w * 0.75 * aspect` | 16 wide is exactly 16 tall at 4:3, 21.3 tall at 16:9 |
| Coordinate precision | whole numbers, per the docs | 1 unit is about 2 px at 1280 wide, decimals buy nothing |
| Forcing 16:9 | `TogglePlayerWidescreen(playerid, true)`, omp >= 1.1.0.2612 | one layout for everyone when you cannot test per display |
| Mobile edges | unknown inset, no query | keep interactive cells inside 20/30/24-unit margins |

## Production Implementation

1. Keep every dimension in one block and derive the ratio once per player:

```pawn
#define UI_SCREEN_W 640.0
#define UI_SCREEN_H 480.0
#define UI_MARGIN_X 20.0
#define UI_MARGIN_TOP 30.0
#define UI_MARGIN_BOTTOM 24.0

stock Float:UI_Aspect(playerid)
{
    new Float:a = GetPlayerCameraAspectRatio(playerid);
    if (a < 1.2) return 1.3333334;                 // unspawned or old client: assume 4:3
    return a;
}

stock Float:UI_SquareH(Float:w, Float:aspect)
{
    return w * (UI_SCREEN_H / UI_SCREEN_W) * aspect;   // 0.75 * aspect
}
```

2. Anchor to the far edge and subtract, instead of centring a fixed width. A right-anchored readout
   moves with the screen; a panel centred at x=320 stays centred but its 21:9 margins collapse:

```pawn
new PlayerText:g_Ammo[MAX_PLAYERS];

stock UI_BuildAmmo(playerid)
{
    if (IsValidPlayerTextDraw(playerid, g_Ammo[playerid]))
        PlayerTextDrawDestroy(playerid, g_Ammo[playerid]);

    new Float:aspect = UI_Aspect(playerid);
    new Float:w = 90.0;
    new Float:h = UI_SquareH(16.0, aspect);
    new Float:x = UI_SCREEN_W - UI_MARGIN_X - w;
    new Float:y = UI_SCREEN_H - UI_MARGIN_BOTTOM - h;

    new PlayerText:td = CreatePlayerTextDraw(playerid, x, y, "AMMO 0");
    PlayerTextDrawAlignment(playerid, td, TEXT_DRAW_ALIGN_LEFT);
    PlayerTextDrawTextSize(playerid, td, x + w, y + h);   // LEFT: absolute corner
    PlayerTextDrawLetterSize(playerid, td, 0.25, 1.1);
    PlayerTextDrawFont(playerid, td, TEXT_DRAW_FONT_1);
    PlayerTextDrawColour(playerid, td, 0xFFFFFFFF);
    PlayerTextDrawSetOutline(playerid, td, 1);
    PlayerTextDrawSetProportional(playerid, td, true);
    PlayerTextDrawShow(playerid, td);
    g_Ammo[playerid] = td;
}
```

3. Use player textdraws for anything whose geometry depends on the ratio. A global draw has one
   geometry for every player, so setting it per player just fights itself:

```pawn
public OnPlayerSpawn(playerid)
{
    UI_BuildAmmo(playerid);          // rebuild: the display setting may have changed while dead
    UI_Report(playerid);
    return 1;
}
```

4. Keep interactive elements inside the margins. On a phone the top 30 units can sit under a notch and
   the bottom 24 under a gesture bar; a HUD label may bleed there, a button may not:

```pawn
stock bool:UI_IsSafe(Float:x, Float:y)
{
    return x >= UI_MARGIN_X && x <= UI_SCREEN_W - UI_MARGIN_X &&
           y >= UI_MARGIN_TOP && y <= UI_SCREEN_H - UI_MARGIN_BOTTOM;
}
```

5. If per-display layouts are out of reach, force one: `TogglePlayerWidescreen(playerid, true)` makes
   the client use the 16:9 layout and every player then shares one geometry. Verify with
   `IsPlayerWidescreenToggled`.

6. Print the ratio you actually got, once per spawn - it is the only way to know which branch ran:

```pawn
stock UI_Report(playerid)
{
    new Float:aspect = UI_Aspect(playerid);
    printf("UI_ASPECT player=%d ratio=%.4f cell_h=%.2f", playerid, aspect, UI_SquareH(16.0, aspect));
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| HUD clipped at 21:9 | fixed left-anchored width, canvas stretched past the design | anchor right/bottom, margins from `UI_` constants |
| Squares look stretched sideways | height copied from width with no aspect term | `h = w * 0.75 * aspect` |
| Text under the notch on a phone | interactive cell above 30 units | clamp with `UI_IsSafe`, keep margins |
| Layout correct for one player, wrong for the next | per-player size applied to a global draw | per-player geometry needs player textdraws |
| Blurry or half-pixel text | decimal coordinates | whole numbers, 1 unit is ~2 px at 1280 |
| Layout wrong after alt-tab or a settings change | built once at connect | rebuild on spawn |
| 21:9 reported as 16:9 and you sized for 21:9 | the native reports the widescreen option, not the display | design for 16:9 extremes, or force the layout |

## Verification

```bash
pawncc /tmp/ui_scale.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/ui_scale.amx
grep -E "UI_ASPECT" server/log.txt
```

Expected: no compiler errors, and one line per spawn whose `cell_h` follows the reported ratio:

```text
UI_ASPECT player=0 ratio=1.7765 cell_h=21.31
UI_ASPECT player=1 ratio=1.3333 cell_h=16.00
```

A 16-unit cell is 16 tall at 4:3 and 21.31 tall at 16:9 - if both players print `cell_h=16.00` while one
of them runs widescreen, the rebuild on spawn is missing.

## Sources (2026)

- https://open.mp/docs/scripting/functions/GetPlayerCameraAspectRatio
- https://open.mp/docs/scripting/functions/TogglePlayerWidescreen
- https://open.mp/docs/scripting/functions/TextDrawCreate
