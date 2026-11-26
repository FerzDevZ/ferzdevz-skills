---
name: textdraw-txd-sprite-atlas-guide
description: Use TXD sprites as TextDraw surfaces.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# TXD sprite atlas

## When to Use
- You need icons or rounded corners without custom models.
- Sprite name or library is wrong.

## 2026 Compatibility & Architecture Matrix
- `TextDrawSetString` with `library:sprite`; classic names include `LD_SPAC:white` and HUD radar icons.
- A wrong library name renders nothing and logs nothing.

## Production Implementation
1. Pick sprites from a known TXD (`LD_SPAC`, `LD_BEAT`, `hud`).
2. Use four `LD_BEAT:chit` corners for rounded boxes.
3. Verify on device, not only in a preview.

```pawn
TextDrawSetString(td, "LD_BEAT:chit");
```

## Deprecated Traps & Edge Cases (2026)
- Assuming any sprite name exists.
- Stretching one sprite for a border instead of four corners.

## Verification
- The sprite renders on a real client; corners keep the radius at both resolutions.
