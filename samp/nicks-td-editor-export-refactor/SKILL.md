---
name: nicks-td-editor-export-refactor
description: Use when NTD exports arrive as flat TextDraw variables.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui, refactor]
    category: samp
---

# Turn an NTD export into modules, not four hundred globals

Nickk's TextDraw Editor (NTD 6.1.1) is a layout tool: you place pixels and it
writes Pawn. The export is a snapshot, not a design — every element arrives as its
own global with literals for coordinates, and a 20-element panel becomes 20
variables you cannot iterate, resize or translate. Treat the export as data to be
imported once, then rebuild it as one module per screen with anchors and arrays.

## When to Use

- NTD exported a flat block of `new Text:` lines with hardcoded coordinates.
- A panel's position must change and every element is a separate literal.
- Per-player HUD elements are global draws, so every player sees the same values.
- The draw pool is near its cap and you need to know what can be shared.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Editor | NTD 6.1.1 (Nickk888SAMP/TextDraw-Editor) | export modes: Simple, Self-working script, Array |
| Dependencies | sscanf2 | the editor itself needs it; the export usually does not |
| Server | open.mp 1.6.7.3218 / SA-MP 0.3.7 | both expose the same textdraw natives |
| Global pool | 2048 `Text:` | `MAX_TEXT_DRAWS` in `omp_textdraw.inc` |
| Player pool | 256 `PlayerText:` per player | `MAX_PLAYER_TEXT_DRAWS` |
| Colour native | `PlayerTextDrawColour`, `TextDrawColour` | `...Color` still compiles with `warning 234` |

## Production Implementation

1. Export in array mode and keep the export file in version control. Array mode
   collapses elements that share a variable name, which is the only part of the
   output worth keeping verbatim.

```text
NTD -> Project -> Export -> Array Export   (writes one array per variable name)
```

2. Decide ownership before writing code: a draw that shows per-player data is a
   `PlayerText:`; a draw that is identical for everyone is a global `Text:`. This
   single decision fixes most of the pool problem.

```pawn
new Text:g_PanelBg;                      // one for the whole server
new PlayerText:g_RowText[MAX_PLAYERS][8]; // per player, 8 rows
```

3. Replace literals with anchors and one row helper. The editor's absolute
   coordinates become offsets from the anchor, so moving the panel is one number.

```pawn
#define PANEL_X      320.0
#define PANEL_Y      120.0
#define ROW_H        18.0
#define ROW_W        180.0

stock PlayerText:CreateRow(playerid, row, const text[])
{
    return CreatePlayerTextDraw(playerid, PANEL_X + 6.0, PANEL_Y + 24.0 + row * ROW_H, text);
}
```

4. Apply style once, in a helper, instead of repeating six calls per element.
   `PlayerTextDrawColour` is the current spelling; the `Color` form is deprecated.

```pawn
stock StyleRow(playerid, PlayerText:td)
{
    PlayerTextDrawColour(playerid, td, 0xFFFFFFFF);
    PlayerTextDrawBackgroundColour(playerid, td, 0x000000FF);
    PlayerTextDrawFont(playerid, td, 1);
    PlayerTextDrawLetterSize(playerid, td, 0.24, 0.9);
    PlayerTextDrawSetOutline(playerid, td, 1);
    return 1;
}
```

5. Build the screen in one function that is safe to call twice: destroy what you
   own first, then create. NTD exports do not do this, so reloading a UI leaks
   pool slots until `MAX_TEXT_DRAWS` is gone.

```pawn
stock BuildPanel(playerid)
{
    for (new i = 0; i < 8; i++)
    {
        if (g_RowText[playerid][i] != INVALID_PLAYER_TEXT_DRAW)
            PlayerTextDrawDestroy(playerid, g_RowText[playerid][i]);
        g_RowText[playerid][i] = CreateRow(playerid, i, " ");
        StyleRow(playerid, g_RowText[playerid][i]);
    }
    return 1;
}
```

6. Keep the editor's placeholder text out of production. NTD writes `_` or
   `LD_SPAC:white` sprites as sizing helpers; if you ship them, they render as
   stray marks in the corner of the screen.

```bash
grep -rn 'LD_SPAC\|"_"' gamemodes/td/ && echo "NTD placeholders remain"
```

7. Draw order is pool order: an element created later covers one created earlier.
   Create backgrounds and boxes first, text second, and do not rely on NTD's
   in-editor layering surviving the export.

```pawn
g_PanelBg = TextDrawCreate(PANEL_X, PANEL_Y, "LD_SPAC:white");
TextDrawTextSize(g_PanelBg, ROW_W, 24.0 + 8 * ROW_H);
```

8. Budget the pool before adding screens: count global draws at compile time and
   keep the per-player count under 256.

```bash
grep -c '^new Text:' gamemodes/td/*.pwn        # global draw declarations
grep -c 'PlayerText:' gamemodes/td/*.pwn       # must stay under 256 per player
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Draws stop appearing after a while | pool exhausted by rebuilding without destroying | destroy owned draws at the top of the build function |
| Every player sees the same value | per-player element exported as global `Text:` | convert to `PlayerText:` arrays |
| Panel is offset on other resolutions | absolute editor coordinates | anchors plus `GetScreenResolution`-aware offsets |
| Stray marks in a corner | NTD placeholder `_` text or `LD_SPAC` sprite kept | strip placeholders, size boxes with `TextDrawTextSize` |
| Text invisible with a box | box created after the text, covering it | create background first, text after |
| Click handling misses the row | hitbox computed from the old literal, not the anchor | derive the hitbox from `PANEL_X`/`ROW_H` in one helper |

## Verification

```bash
grep -c 'new Text:' gamemodes/td/*.pwn
grep -rn 'LD_SPAC' gamemodes/td/ || echo "no placeholders"
pawncc -i$HOME/samp-sdk/omp-stdlib -d3 '-;+' '-(' gamemodes/td/panel.pwn -opanel.amx
```

- The global count is the number of shared draws you intend, not the number of
  elements in the editor project.
- `no placeholders` and a clean `pawncc` run.
- In game, `/panel` twice in a row shows the same layout — proof that the build
  function destroys before it recreates.

## Sources (2026)

- https://github.com/Nickk888SAMP/TextDraw-Editor
- https://github.com/Nickk888SAMP/TextDraw-Editor/releases/tag/6.1.1
- https://open.mp/docs/scripting/resources/textdraws
