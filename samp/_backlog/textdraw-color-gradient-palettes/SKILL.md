---
name: textdraw-color-gradient-palettes
description: Pick readable colours and gradients for TextDraws.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# colour palettes

## When to Use
- Text is unreadable on some backgrounds.
- Gradients band or look like AI slop.

## 2026 Compatibility & Architecture Matrix
- Colours are ARGB hex; text over panels needs ≥4.5:1 contrast.
- Gradients need 3–4 stops and a flat base to avoid banding.

## Production Implementation
1. Define `UI_*` colour constants once.
2. Pick a base, surface and accent with measured contrast.
3. Avoid violet/indigo hero gradients; use brand-neutral surfaces.

```pawn
#define UI_BG 0x101418FF
#define UI_TEXT 0xF2F5F7FF
#define UI_ACCENT 0xFF8A00FF
```

## Deprecated Traps & Edge Cases (2026)
- Outline + shadow + low contrast at once.
- Alpha in the wrong byte order (RGBA vs ARGB).

## Verification
- Contrast ratio measured for each text/surface pair; no colour literals outside the token file.
