---
name: exterior-world-lod-drawdistance
description: Keep exteriors from flickering at distance.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# LOD and draw distance

## When to Use
- Objects flicker or disappear at range.
- LOD models overlap the real ones.

## 2026 Compatibility & Architecture Matrix
- `drawdistance` should exceed `streamdistance` for large landmarks, within streamer limits.
- LOD objects need their own world/interior filtering.

## Production Implementation
1. Set short distances for props and long for landmarks.
2. Remove or hide LOD when the real model streams in.
3. Measure FPS and visible objects per player.

```pawn
CreateDynamicObject(model, x, y, z, 0, 0, 0, world, interior, -1, 300.0, 500.0);
```

## Deprecated Traps & Edge Cases (2026)
- One global distance for everything.
- LOD and full model both visible, causing z-fighting.

## Verification
- No flicker at the configured distance; visible object count stays bounded.
