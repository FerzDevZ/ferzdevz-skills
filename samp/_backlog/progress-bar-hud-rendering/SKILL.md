---
name: progress-bar-hud-rendering
description: Render a progress bar with boxes, not glyphs.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# progress bar

## When to Use
- Bar width does not match the value.
- Bar flickers when updated.

## 2026 Compatibility & Architecture Matrix
- Box width is set through `PlayerTextDrawTextSize` on a `UseBox` draw.
- Refresh only when the value changes.

## Production Implementation
1. Create the background box and the fill box once.
2. Update the fill width as `max_width * pct`.
3. Clamp 0..100 before computing.

```pawn
PlayerTextDrawTextSize(playerid, g_Fill, WIDTH * pct / 100.0, 6.0);
PlayerTextDrawShow(playerid, g_Fill);
```

## Deprecated Traps & Edge Cases (2026)
- Recreating the draw every update.
- Unclamped percentage producing a box past the background.

## Verification
- 0% and 100% match the background edges.
- No flicker during a timed update.
