---
name: texture-studio-export-optimizer
description: Export Texture Studio maps without bloat.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# Texture Studio export

## When to Use
- Exports contain thousands of `CreateObject` calls and duplicate materials.
- Start-up takes minutes.

## 2026 Compatibility & Architecture Matrix
- Convert to `CreateDynamicObject` and deduplicate materials.
- Object count and material slots per object are limited.

## Production Implementation
1. Export, then run a converter that rewrites to streamer calls.
2. Deduplicate identical material entries and merge rows.
3. Load in batches and verify the count.

```pawn
CreateDynamicObject(model, x, y, z, rx, ry, rz, world, interior, -1, 200.0);
```

## Deprecated Traps & Edge Cases (2026)
- Keeping static `CreateObject` for thousands of items.
- Material slot index reused for two different materials.

## Verification
- Object count matches the source and start-up is under the budget.
