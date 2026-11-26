---
name: samp-model-selection-ui
description: Use when a skin or vehicle picker needs real previews.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, ui, textdraw, models, preview, mselection]
    category: samp
---

# A preview grid is a TextDraw row, not a dialog list

`TEXT_DRAW_FONT_MODEL_PREVIEW` renders a live 3D model inside a TextDraw, so a picker is a grid
of TextDraws plus `SelectTextDraw` and one `OnPlayerClickTextDraw` handler. Each cell's
clickable area is exactly `TextDrawTextSize`, so hit detection is arithmetic on the TextDraw id.

## When to Use

- A shop, garage or character creator must show models visually instead of names in a list.
- Players report "the menu opens but every preview is invisible".
- Clicks land on the wrong cell, or Escape leaves the cursor on screen.
- You want the picker without the mSelection plugin (`ShowModelSelectionMenuEx` and friends).

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Preview font | `TEXT_DRAW_FONT_MODEL_PREVIEW` (5) | `TextDrawSetPreviewModel` does nothing on another font |
| Selection | `TextDrawSetSelectable` → `SelectTextDraw` | selectable must be set before the first show |
| Model range | 0-311 skins, 400-611 vehicles | 20000+ is 0.3.DL / open.mp custom models |

## Production Implementation

1. Fix the geometry once. Cells are created in one contiguous run, so an id difference is a
   cell index and the hitbox is never recomputed:

```pawn
#define CELLS_PER_PAGE 20
#define GRID_X 92.0
#define GRID_Y 108.0
#define GAP_X  74.0
#define GAP_Y  88.0
#define CELL_W 62.0
#define CELL_H 78.0

new g_SkinList[] = { 0, 1, 2, 7, 12, 21, 23, 29, 36, 47, 60, 63, 101, 105, 137, 149, 166, 170, 188, 199 };
new Text:g_Cell[CELLS_PER_PAGE];
new g_CellModel[CELLS_PER_PAGE];
new bool:g_Picking[MAX_PLAYERS];
```

2. Build the cells at start-up: `TextDrawTextSize` is the clickable rectangle and must be
   non-zero, and `TextDrawSetSelectable` must run before the first show:

```pawn
stock BuildSkinGrid()
{
    new Float:x, Float:y;
    for (new i; i < CELLS_PER_PAGE; i++)
    {
        x = GRID_X + (i % 5) * GAP_X;
        y = GRID_Y + (i / 5) * GAP_Y;
        g_Cell[i] = TextDrawCreate(x, y, "_");
        TextDrawFont(g_Cell[i], TEXT_DRAW_FONT_MODEL_PREVIEW);
        TextDrawTextSize(g_Cell[i], CELL_W, CELL_H);      // clickable area
        TextDrawBackgroundColor(g_Cell[i], 0x2A2A2AFF);
        TextDrawSetSelectable(g_Cell[i], true);           // before the first show
    }
    return 1;
}
```

3. Fill a page, then enter select mode — `SelectTextDraw` shows the cursor, without it the cells
   are visible but inert:

```pawn
stock ShowSkinPage(playerid, page)
{
    new idx = page * CELLS_PER_PAGE;
    for (new i; i < CELLS_PER_PAGE && idx < sizeof g_SkinList; i++, idx++)
    {
        g_CellModel[i] = g_SkinList[idx];
        TextDrawSetPreviewModel(g_Cell[i], g_SkinList[idx]);
        TextDrawSetPreviewRot(g_Cell[i], -10.0, 0.0, -20.0, 1.0);
        TextDrawShowForPlayer(playerid, g_Cell[i]);
    }
    g_Picking[playerid] = true;
    SelectTextDraw(playerid, 0xFF8C1AFF);
    return 1;
}
```

4. Resolve the click by id arithmetic, then re-validate the model server-side:

```pawn
public OnPlayerClickTextDraw(playerid, Text:clickedid)
{
    if (!g_Picking[playerid]) return 0;

    if (clickedid == INVALID_TEXT_DRAW)                 // Escape
    {
        CloseModelMenu(playerid);
        return 1;
    }

    new idx = _:clickedid - _:g_Cell[0];
    if (idx < 0 || idx >= CELLS_PER_PAGE || _:g_Cell[idx] != _:clickedid) return 1;

    new model = g_CellModel[idx], bool:allowed = false;
    for (new i; i < sizeof g_SkinList; i++)
        if (g_SkinList[i] == model) allowed = true;

    if (!allowed) return 1;                             // never applied: not on this page
    SetPlayerSkin(playerid, model);
    CloseModelMenu(playerid);
    return 1;
}
```

5. Close in one place: clear the flag, cancel selection, hide the cells. Never call
   `CancelSelectTextDraw` unconditionally inside the callback — it re-enters and loops:

```pawn
stock CloseModelMenu(playerid)
{
    if (!g_Picking[playerid]) return 0;
    g_Picking[playerid] = false;
    CancelSelectTextDraw(playerid);
    for (new i; i < CELLS_PER_PAGE; i++) TextDrawHideForPlayer(playerid, g_Cell[i]);
    return 1;
}
```

6. Vehicles reuse the grid with `TextDrawSetPreviewVehCol` and a handler that stores the model
   instead of calling `SetPlayerSkin`.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every preview is blank | font never set to `TEXT_DRAW_FONT_MODEL_PREVIEW` | set the font before the model |
| Cells visible but nothing clickable | `TextDrawSetSelectable` after the first show, or `TextDrawTextSize` zero | set both before showing, both non-zero |
| Cursor never disappears | `CancelSelectTextDraw` skipped on the Escape branch | call it from one close stock |
| Click applies the neighbouring skin | index computed from a stale or non-contiguous id range | assert `_:g_Cell[0] + i == _:g_Cell[i]` at build time |
| Client picks a model you never offered | the index is trusted instead of re-checked | re-validate `g_CellModel[idx]` before applying |
| First cell looks empty | model 0 (CJ) renders late on some clients | it is valid — test it explicitly |

## Verification

Audit the list before shipping — skins are 0-311 and 265-299 are cutscene-only:

```bash
python3 scripts/check_model_list.py scriptfiles/skins.txt ; echo "exit=$?"
```

```text
skins: 20 models, 0 duplicates, 0 problems
exit=0
```

Then in game: open the picker, confirm all 20 previews render on the lowest-end device, click the
first and last cell and get exactly those models, press Escape and confirm the cursor is gone.

## Sources (2026)

- https://open.mp/docs/scripting/functions/TextDrawSetPreviewModel — the preview font requirement, model/vehicle/object examples.
- https://open.mp/docs/scripting/functions/SelectTextDraw — `TextDrawSetSelectable` first, and that the text (not the box) is highlighted.
- https://open.mp/docs/scripting/callbacks/OnPlayerClickTextDraw — `INVALID_TEXT_DRAW` on cancel, and the warning against unconditional `CancelSelectTextDraw`.
