---
name: ntd-project-to-modular-include
description: Turn an NTD project into a reusable include.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# NTD to include

## When to Use
- The same HUD is copied between gamemodes.
- Editor and production code drift apart.

## 2026 Compatibility & Architecture Matrix
- One include per screen with `Show`/`Hide`/`Update` API.
- Global cap 2048 shared by all includes.

## Production Implementation
1. Define the public API (`ui_Inventory_Show(playerid)`), keep draw ids private.
2. Create draws lazily on first show and destroy on module unload.
3. Ship an example gamemode using only the public functions.

```pawn
stock ui_Inventory_Show(playerid) { if (!g_built[playerid]) Build(playerid); }
```

## Deprecated Traps & Edge Cases (2026)
- Exposing raw draw ids so callers mutate them.
- Creating draws for every player at start-up.

## Verification
- Example compiles against the include only; peak pool usage is documented.
