---
name: clickable-textdraw-inventory
description: Use when a clickable inventory grid picks the wrong slot.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw, ui, inventory]
    category: samp
---

# Clickable TextDraw inventory grid

## When to Use

- Clicks select the neighbouring cell, or the first cell never responds at all.
- The cursor stays captured after closing the bag, or a fast double click duplicates an item.

## Compatibility & Stack Matrix (2026)

| Piece | Call | Why it matters |
| --- | --- | --- |
| Grid owner | player textdraws, 256 per player | 49 cells cost 49 of 256, the global pool stays free |
| Hitbox | `PlayerTextDrawTextSize` | defines the click rectangle even with no box |
| Selectable + click | `PlayerTextDrawSetSelectable` then `OnPlayerClickPlayerTextDraw` | set before `SelectTextDraw`; the id is the handle |
| ESC | `OnPlayerClickTextDraw` with `INVALID_TEXT_DRAW` | ESC never reaches the player-textdraw callback |
| Geometry | 46x42 cells on a 52-unit pitch from (138, 90) | 49 cells end at (496, 444), inside 640x480 |

## Production Implementation

1. Derive every cell from the slot index so the mapping cannot drift:

```pawn
#define INV_COLS 7
#define INV_SLOTS 49
#define INV_PITCH 52.0
#define INV_CELL_W 46.0
#define INV_CELL_H 42.0
#define INV_ANCHOR_X 138.0
#define INV_ANCHOR_Y 90.0

new PlayerText:g_Cell[MAX_PLAYERS][INV_SLOTS];
new g_Item[MAX_PLAYERS][INV_SLOTS];
new g_Count[MAX_PLAYERS][INV_SLOTS];
new bool:g_Open[MAX_PLAYERS];

stock Float:Inv_CellX(slot) { return INV_ANCHOR_X + float(slot % INV_COLS) * INV_PITCH; }
stock Float:Inv_CellY(slot) { return INV_ANCHOR_Y + float(slot / INV_COLS) * INV_PITCH; }
```

2. Build once per player. Each cell keeps one character of text, because the text is what highlights:

```pawn
stock Inv_Label(playerid, slot)
{
    new label[8] = " ";
    if (g_Count[playerid][slot] > 0) format(label, sizeof label, "%d", g_Count[playerid][slot]);
    PlayerTextDrawSetString(playerid, g_Cell[playerid][slot], label);
}
stock Inv_Build(playerid)
{
    for (new i = 0; i < INV_SLOTS; i++)
    {
        if (IsValidPlayerTextDraw(playerid, g_Cell[playerid][i]))
            PlayerTextDrawDestroy(playerid, g_Cell[playerid][i]);
        new Float:x = Inv_CellX(i);
        new Float:y = Inv_CellY(i);
        new PlayerText:td = CreatePlayerTextDraw(playerid, x, y, " ");
        PlayerTextDrawAlignment(playerid, td, TEXT_DRAW_ALIGN_LEFT);
        PlayerTextDrawTextSize(playerid, td, x + INV_CELL_W, y + INV_CELL_H);
        PlayerTextDrawLetterSize(playerid, td, 0.2, 1.0);
        PlayerTextDrawColour(playerid, td, 0xFFFFFFFF);
        PlayerTextDrawUseBox(playerid, td, true);
        PlayerTextDrawBoxColour(playerid, td, 0x000000C8);
        PlayerTextDrawSetSelectable(playerid, td, true);
        g_Cell[playerid][i] = td;
    }
}
```

3. Open shows every cell before capturing the cursor; `Inv_Close` is the only path that releases it:

```pawn
stock Inv_Open(playerid)
{
    if (g_Open[playerid]) return 0;
    if (!IsValidPlayerTextDraw(playerid, g_Cell[playerid][0])) Inv_Build(playerid);
    for (new i = 0; i < INV_SLOTS; i++)
    {
        Inv_Label(playerid, i);
        PlayerTextDrawShow(playerid, g_Cell[playerid][i]);
    }
    g_Open[playerid] = true;
    SelectTextDraw(playerid, 0xFFFFFFAA);
    return 1;
}
stock Inv_Close(playerid)
{
    if (!g_Open[playerid]) return 0;
    for (new i = 0; i < INV_SLOTS; i++) PlayerTextDrawHide(playerid, g_Cell[playerid][i]);
    g_Open[playerid] = false;
    CancelSelectTextDraw(playerid);
    return 1;
}
```

4. Map the handle back through your own array and re-validate - the label is decoration, the arrays are
   the truth:

```pawn
stock Inv_SlotFromDraw(playerid, PlayerText:td)
{
    for (new i = 0; i < INV_SLOTS; i++)
        if (g_Cell[playerid][i] == td) return i;
    return -1;                               // -1, not 0: slot 0 is a valid cell
}
stock Inv_Use(playerid, slot)
{
    if (slot < 0 || slot >= INV_SLOTS || !g_Open[playerid]) return 0;
    if (g_Count[playerid][slot] <= 0) return 0;
    g_Count[playerid][slot]--;
    if (g_Count[playerid][slot] == 0) g_Item[playerid][slot] = 0;
    Inv_Label(playerid, slot);
    return 1;
}
public OnPlayerClickPlayerTextDraw(playerid, PlayerText:playertextid)
{
    if (!g_Open[playerid]) return 0;          // a dialog or another panel owns the cursor
    new slot = Inv_SlotFromDraw(playerid, playertextid);
    if (slot < 0) return 0;
    Inv_Use(playerid, slot);
    return 1;                                 // handled even when refused
}
public OnPlayerClickTextDraw(playerid, Text:clickedid)
{
    if (clickedid == INVALID_TEXT_DRAW) Inv_Close(playerid);   // ESC
    return 0;
}
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Click selects the neighbour | slot inferred from coordinates, or boxes overlap | map the handle through `Inv_SlotFromDraw`, keep the 52 pitch |
| Cell 0 never responds | `0` used as the not-found sentinel | return `-1` and test `slot < 0` |
| Cursor stuck after closing | `CancelSelectTextDraw` missing on one path | close through `Inv_Close` only |
| Empty cell triggers a use | handler trusts the label or ignores the count | reject when `g_Count` is 0 |
| Double click duplicates an item | the draw refreshes after the second click lands | decrement first, refresh immediately, re-validate |
| Grid clicks fire over a dialog | no panel-state guard | return 0 early when `g_Open` is false |

## Verification

```bash
pawncc /tmp/inv.pwn -i"$HOME/samp-sdk/omp-stdlib" -o/tmp/inv.amx
grep -E "INV_(PITCH|ANCHOR_X|ANCHOR_Y)" gamemodes/inv.pwn
```

Expected: no compiler errors and the three `#define` lines read `52.0`, `138.0`, `90.0`; that places cell
48 at (450, 402) with a click rectangle ending at (496, 444), matching the probe
`INV_GRID cells=49 first=(138.0,90.0) last=(450.0,402.0)`. In game the bottom-right cell must log slot 48,
ESC must close and return the cursor, and three clicks on a count of 2 must leave 0, not -1.

## Sources (2026)

- https://open.mp/docs/scripting/callbacks/OnPlayerClickPlayerTextDraw
- https://open.mp/docs/scripting/functions/SelectTextDraw
- https://open.mp/docs/scripting/functions/PlayerTextDrawTextSize
