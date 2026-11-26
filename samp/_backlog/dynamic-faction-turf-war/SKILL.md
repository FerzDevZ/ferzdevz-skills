---
name: dynamic-faction-turf-war
description: Model turf ownership and capture.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# turf war

## When to Use
- Turf changes without players present.
- Capture progress duplicates.

## 2026 Compatibility & Architecture Matrix
- Ownership + capture progress are server state with timers.
- Require a minimum attacker count and presence check.

## Production Implementation
1. Track attackers/defenders in the zone.
2. Advance progress only when the requirement is met.
3. Persist ownership on change.

```pawn
if (attackers >= MIN_ATTACKERS) progress += step;
```

## Deprecated Traps & Edge Cases (2026)
- Capture by a single player who left.
- Progress reset on server restart without persistence.

## Verification
- Capture requires presence for the full duration.
- Ownership survives a restart.
