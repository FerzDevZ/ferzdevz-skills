---
name: mapandreas-colandreas-raycast
description: Use height and collision data for raycasts.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, world]
    category: samp
---

# MapAndreas / ColAndreas

## When to Use
- You need ground height or a collision raycast.
- Objects are custom and native collision misses them.

## 2026 Compatibility & Architecture Matrix
- MapAndreas gives terrain height; ColAndreas gives collision against models.
- Custom objects need ColAndreas, not MapAndreas.

## Production Implementation
1. Load the height data at start.
2. Use ColAndreas for object collisions and ground checks.
3. Cache results per position where possible.

```pawn
new Float:z; MapAndreas_FindZ_For2DCoord(x, y, z);
```

## Deprecated Traps & Edge Cases (2026)
- Using MapAndreas height for an interior floor.
- Raycasting every tick.

## Verification
- Ground checks match visual terrain in a sample of coordinates.
- Collision tests on custom objects return hits.
