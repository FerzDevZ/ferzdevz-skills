---
name: mission-quest-objective-tracker
description: Track multi-step objectives reliably.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# quest tracker

## When to Use
- Objectives complete out of order.
- Progress lost on reconnect.

## 2026 Compatibility & Architecture Matrix
- Objective list per quest with explicit states.
- Server validates each objective trigger.

## Production Implementation
1. Store quest id, step and counters per player.
2. Advance only on the matching trigger.
3. Persist progress and restore on login.

```pawn
if (step == 2 && event == EV_DELIVER) AdvanceQuest(playerid);
```

## Deprecated Traps & Edge Cases (2026)
- Completing a later step skipping earlier ones.
- Progress in memory only.

## Verification
- Objectives complete in order only.
- Relogin restores the step.
