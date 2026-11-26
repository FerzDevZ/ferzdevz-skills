---
name: dynamic-zone-area-triggers
description: Trigger actions on dynamic areas.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer]
    category: samp
---

# dynamic areas

## When to Use
- Zone entry fires repeatedly or never.
- Areas need per-world/interior separation.

## 2026 Compatibility & Architecture Matrix
- Streamer areas support world/interior filtering and callbacks.
- A player can be inside two overlapping areas.

## Production Implementation
1. Create areas with explicit world/interior ids.
2. Debounce entry/exit and track the previous state.
3. Log transitions with playerid and area id.

```pawn
CreateDynamicCircle(x, y, 50.0, worldid, interiorid, -1);
```

## Deprecated Traps & Edge Cases (2026)
- Triggering on every tick inside the area.
- No exit handling leaves stale state.

## Verification
- One entry event per crossing.
- Overlapping areas both report correctly.
