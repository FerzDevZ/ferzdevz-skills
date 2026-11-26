---
name: housing-basebuilding-streamer
description: Build player housing with streamed furniture.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# housing

## When to Use
- Furniture disappears after restart.
- Two players edit the same house.

## 2026 Compatibility & Architecture Matrix
- Persist each furniture row with house id, model and transform.
- Stream per house world; lock editing per player.

## Production Implementation
1. Load on house enter and create dynamically.
2. Save on place/move/remove.
3. Destroy on exit to keep the budget.

```pawn
CreateDynamicObject(model, x, y, z, rx, ry, rz, house_world, interior, -1, 100.0);
```

## Deprecated Traps & Edge Cases (2026)
- Global objects for every house.
- Editing without an ownership lock.

## Verification
- Furniture count after restart matches the DB.
- Only one editor at a time.
