---
name: nicks-td-editor-export-refactor
description: Refactor Nick's TextDraw Editor exports into modules.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# NTD export refactor

## When to Use
- NTD 6.1.x export produced flat `new Text:` lines with hardcoded coordinates.
- You need maintainable arrays instead of one-off variables.

## 2026 Compatibility & Architecture Matrix
- NTD (Nickk888SAMP/TextDraw-Editor, NTD 6.1.1) exports a simple script or a self-working script, plus array-export mode.
- Global TextDraw cap 2048; PlayerTextDraw hard cap 256 per player.

## Production Implementation
1. Export with array mode where possible, then group elements by screen.
2. Replace literals with anchor defines and per-row helpers.
3. Move per-player elements to `PlayerText:` arrays.

```pawn
#define TD_TITLE_X 320.0
new PlayerText:g_Title[MAX_PLAYERS];
g_Title[playerid] = CreatePlayerTextDraw(playerid, TD_TITLE_X, 40.0, "Inventory");
```

## Deprecated Traps & Edge Cases (2026)
- Pasting the export as-is: every element becomes a global draw.
- Keeping NTD's dummy text and forgetting to `Hide`.

## Verification
- The refactored module renders identically and pool usage drops.
- No unused exported draws remain (grep for the NTD prefix).
