---
name: survival-vitals-hunger-infection
description: Add survival vitals without runaway timers.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# survival vitals

## When to Use
- Hunger/thirst ticks leak timers.
- Vitals reset unexpectedly on respawn.

## 2026 Compatibility & Architecture Matrix
- One timer per player with a single state update.
- Persist vitals with the account.

## Production Implementation
1. Update vitals on a slow timer (5–10 s).
2. Apply effects at thresholds and log them.
3. Persist on save and restore on spawn.

```pawn
task Vitals[5000](playerid) { g_Hunger[playerid] -= 1; }
```

## Deprecated Traps & Edge Cases (2026)
- Multiple timers modifying the same vital.
- Effects applying every tick at a threshold.

## Verification
- One timer per player, killed on disconnect.
- Vitals restore after reconnect.
