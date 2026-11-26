---
name: live-hotfix-filterscript
description: Ship a hotfix without a full restart.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# hotfix filterscript

## When to Use
- A critical bug needs an immediate fix.
- A restart is too disruptive.

## 2026 Compatibility & Architecture Matrix
- A filterscript can load/unload at runtime but cannot replace gamemode callbacks.
- State ownership must be explicit.

## Production Implementation
1. Move the fix into a filterscript using `CallRemoteFunction` hooks.
2. Load and verify, then merge into the gamemode.
3. Log the hotfix version at load.

```pawn
SendRconCommand("loadfs hotfix_2026_11");
```

## Deprecated Traps & Edge Cases (2026)
- Hotfix and gamemode both handling one callback.
- Forgetting to unload after the release.

## Verification
- The hotfix logs its version and the bug stops; unloading removes duplicate behaviour.
