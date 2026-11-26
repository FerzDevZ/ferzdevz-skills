---
name: inventory-weight-slot-engine
description: Build an inventory with weight and slots.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# inventory engine

## When to Use
- Items duplicate on move or drop.
- Weight limits bypassed by stacking.

## 2026 Compatibility & Architecture Matrix
- Slots plus weight; both validated server-side.
- Item definitions in one table include weight and stack size.

## Production Implementation
1. Validate slot index and weight before adding.
2. Move items in one transaction.
3. Log every add/remove with a reference.

```pawn
if (total_weight + item.weight > MAX_WEIGHT) return 0;
```

## Deprecated Traps & Edge Cases (2026)
- Trusting the client's drag-and-drop order.
- Unbounded stack size.

## Verification
- Overweight adds are rejected.
- A drop/move test keeps total count constant.
