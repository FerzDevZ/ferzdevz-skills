---
name: textdraw-zorder-layer-stacking
description: Control TextDraw layer order.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# z-order

## When to Use
- Text appears behind its panel.
- Some clients draw in creation order, others by id.

## 2026 Compatibility & Architecture Matrix
- Order is creation/`TextDrawSetOutline` independent; show order and ids matter.
- Rebuild in the intended order when elements are recreated.

## Production Implementation
1. Create background surfaces first, text after.
2. Keep ids monotonic per panel; document the order.
3. Test after a destroy/recreate cycle.

```pawn
// create background, then border, then text
```

## Deprecated Traps & Edge Cases (2026)
- Recreating one element later and expecting it to stay underneath.
- Relying on `TextDrawSetOutline` to fix layering.

## Verification
- Reopening a panel keeps the intended stacking on two clients.
