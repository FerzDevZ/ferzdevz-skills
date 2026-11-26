---
name: 3d-text-label-streaming
description: Stream 3D labels with a distance budget.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, streamer]
    category: samp
---

# 3D labels

## When to Use
- Labels pop in or cost FPS in crowded areas.
- Thousands of labels are created at start.

## 2026 Compatibility & Architecture Matrix
- Streamer 2.9.6 handles 3D labels with per-player streaming distance.
- Native label limits are far lower than streamed ones.

## Production Implementation
1. Create labels through the streamer with a short distance.
2. Batch-create at start and destroy on unload.
3. Measure visible labels per player.

```pawn
CreateDynamic3DTextLabel("Shop", 0xFFFFFFFF, x, y, z, 20.0);
```

## Deprecated Traps & Edge Cases (2026)
- A global label for every object in the map.
- Distance large enough to render the whole city.

## Verification
- Visible label count per player stays bounded.
- No pop-in at the configured distance.
