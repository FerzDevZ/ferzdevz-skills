---
name: dynamic-object-material-text-signs
description: Render dynamic signs with material text.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# material text

## When to Use
- Signs need per-business text.
- Text is blurry or invisible at distance.

## 2026 Compatibility & Architecture Matrix
- `SetDynamicObjectMaterialText` supports font, size, colour and resolution.
- Text resolution and font size determine legibility.

## Production Implementation
1. Use a flat object as the sign surface.
2. Set material text with an explicit font and size.
3. Update text when the business changes and persist it.

```pawn
SetDynamicObjectMaterialText(obj, 0, "24/7 Store", 130, "Arial", 48, 1, 0xFFFFFFFF, 0, 1);
```

## Deprecated Traps & Edge Cases (2026)
- Updating the material every tick.
- Text longer than the surface resolution.

## Verification
- Sign text is readable from the intended distance and updates once per change.
