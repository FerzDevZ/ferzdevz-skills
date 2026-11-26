---
name: death-injury-knockdown-state
description: Model death, injury and knockdown separately.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, combat]
    category: samp
---

# injury state

## When to Use
- Players die instantly instead of being injured.
- Knockdown state conflicts with death.

## 2026 Compatibility & Architecture Matrix
- Health <= 0 is death; a knockdown is a temporary state with a timer.
- State machine prevents double handling.

## Production Implementation
1. Add an `injured` state with a timer and movement cap.
2. Cancel on damage or revive; log transitions.
3. Restore state on respawn.

```pawn
if (health <= 0.0) EnterDeathState(playerid); else if (health < 25.0) EnterInjured(playerid);
```

## Deprecated Traps & Edge Cases (2026)
- Two systems both applying death.
- An injured timer surviving respawn.

## Verification
- One death event per death.
- Injured state ends on revive or timer.
