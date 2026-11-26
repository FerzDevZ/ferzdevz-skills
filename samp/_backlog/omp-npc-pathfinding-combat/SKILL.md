---
name: omp-npc-pathfinding-combat
description: Drive NPC paths and combat in open.mp.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, npc]
    category: samp
---

# NPC path/combat

## When to Use
- NPCs must patrol, aim and fight.
- Movement looks like teleporting.

## 2026 Compatibility & Architecture Matrix
- Verified API includes NPC_CreatePath, NPC_AddPointToPath, NPC_AimAt, NPC_AimAtPlayer, NPC_EnableInfiniteAmmo, NPC_EnableReloading, NPC_EnterVehicle.
- Path following is asynchronous; use callbacks rather than polling.

## Production Implementation
1. Build a path once, then start movement.
2. Set weapon/ammo and aiming per state.
3. Handle finish callbacks to loop the patrol.

```pawn
new path = NPC_CreatePath();
NPC_AddPointToPath(path, x, y, z);
// start following: take the exact function name from your omp_npc.inc
// (grep -n "path" includes/omp_npc.inc); NPC_StartPath is NOT in the 1.6 docs.
```

## Deprecated Traps & Edge Cases (2026)
- Rebuilding the path every tick.
- Aiming at a disconnected player.

## Verification
- NPC walks the route and the finish callback fires.
- Combat consumes ammo unless infinite ammo is enabled.
