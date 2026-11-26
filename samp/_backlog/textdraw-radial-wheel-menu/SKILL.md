---
name: textdraw-radial-wheel-menu
description: Build a radial menu with TextDraws.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# radial menu

## When to Use
- A radial menu selects the wrong slice.
- It opens under the finger and blocks movement.

## 2026 Compatibility & Architecture Matrix
- Slices are positioned by angle; selection uses the pointer vector, not the nearest draw id.
- Mobile needs a touch gate and a cancel gesture.

## Production Implementation
1. Place slices around a centre with a fixed radius.
2. Map the touch angle to a slice index and highlight it.
3. Cancel on release outside the ring or on back.

```pawn
new Float:ang = atan2(ty - cy, tx - cx);
new slice = floatround((ang + PI) / (2*PI) * SLICES) % SLICES;
```

## Deprecated Traps & Edge Cases (2026)
- Hit-testing each slice draw individually at small angles.
- Leaving the cursor captured after close.

## Verification
- Every slice is selectable at 360°; closing restores movement.
