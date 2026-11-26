---
name: custom-interior-shell-builder
description: Build custom interiors that do not leak.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# interior shell

## When to Use
- Custom interior is visible from outside.
- Players fall through the shell.

## 2026 Compatibility & Architecture Matrix
- A shell is an object set in its own world/interior plus collision.
- Doors are teleports with solid facades on both sides.

## Production Implementation
1. Build the shell in a dedicated world and interior id.
2. Add collision (ColAndreas or COL) and test walking the perimeter.
3. Route the entrance/exit with a streamer update.

```pawn
SetPlayerVirtualWorld(playerid, INTERIOR_WORLD); SetPlayerInterior(playerid, INTERIOR_ID);
```

## Deprecated Traps & Edge Cases (2026)
- Relying on visual walls without collision.
- Sharing a world with the exterior.

## Verification
- The shell is invisible from outside; the player cannot fall out.
