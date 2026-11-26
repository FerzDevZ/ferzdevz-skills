---
name: textdraw-preview-model-3d-rigging
description: Render 3D model previews in TextDraws.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# TextDraw preview model

## When to Use
- You need a rotating skin/vehicle preview.
- The preview is blurry, wrong-facing or invisible.

## 2026 Compatibility & Architecture Matrix
- `PlayerTextDrawSetPreviewModel` + `SetPreviewRot` + `SetPreviewVehCol`; requires the model to be loaded.
- Preview draws need `TextSize` and `UseBox` consistent with the sprite.

## Production Implementation
1. Create the draw as a box with the preview model set.
2. Set rotation per frame on a timer, not every tick.
3. Load the model before showing the preview.

```pawn
PlayerTextDrawSetPreviewModel(playerid, td, 411);
PlayerTextDrawSetPreviewRot(playerid, td, 0.0, 0.0, 0.0, 1.0);
```

## Deprecated Traps & Edge Cases (2026)
- Previewing a model the client has not streamed.
- Rebuilding the draw to change rotation.

## Verification
- The preview shows the model and rotates smoothly; no flicker at 5 FPS of updates.
