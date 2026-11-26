---
name: global-vs-player-td-budget
description: Pick the right pool and stay under the cap.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# TD budget

## When to Use
- HUD flickers between players.
- Global cap is reached at start-up.

## 2026 Compatibility & Architecture Matrix
- Global textdraws: 2048 total; PlayerTextDraw: 256 per player, keep 200.
- Per-player values must be PlayerTD.

## Production Implementation
1. Classify each element as shared or per-player.
2. Move anything holding player data to PlayerTD.
3. Log pool usage at start-up and in a debug command.

```pawn
new PlayerText:g_Money[MAX_PLAYERS];
g_Money[playerid] = CreatePlayerTextDraw(playerid, 500.0, 30.0, "0");
```

## Deprecated Traps & Edge Cases (2026)
- One global draw updated inside a loop for all players.
- Assuming 2048 is per player.

## Verification
- Pool usage is logged and under budget with every screen open.
- Values differ per player in a two-client test.
