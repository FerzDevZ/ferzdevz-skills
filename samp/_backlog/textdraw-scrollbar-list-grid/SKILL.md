---
name: textdraw-scrollbar-list-grid
description: Build a scrollable list or grid in TextDraws.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# scrollbar list

## When to Use
- Lists overflow the panel.
- Scrolling desynchronises the selection.

## 2026 Compatibility & Architecture Matrix
- Rows are PlayerTDs reused by index; the scroll offset is per player.
- Hitboxes must be recomputed after scrolling.

## Production Implementation
1. Render only visible rows and bind them to `offset + i`.
2. Add scroll buttons/keys and clamp the offset.
3. Recompute the selected item from the offset, not from the visual id.

```pawn
new idx = g_Offset[playerid] + row; if (idx >= g_Count) return;
```

## Deprecated Traps & Edge Cases (2026)
- Creating a draw per item instead of reusing rows.
- Selection stored as a screen row instead of a data index.

## Verification
- Scrolling 100 items keeps the pool flat and the selection correct.
