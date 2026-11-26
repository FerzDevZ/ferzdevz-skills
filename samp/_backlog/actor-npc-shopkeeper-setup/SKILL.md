---
name: actor-npc-shopkeeper-setup
description: Place actors and NPCs for shops.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, actors]
    category: samp
---

# actors and NPCs

## When to Use
- A shopkeeper is static and does not react.
- NPCs are needed for ambient behaviour.

## 2026 Compatibility & Architecture Matrix
- `CreateActor` is a static actor; open.mp `NPC_Create` (since v1.5.8.3079) is a simulated player.
- NPCs consume player slots.

## Production Implementation
1. Use actors for static shopkeepers and NPCs for behaviour.
2. Set facing angle and animation for actors.
3. For NPCs, spawn, set pos and weapon, and track ids.

```pawn
new actor = CreateActor(skin, x, y, z, angle);
ApplyActorAnimation(actor, "PED", "IDLE_STANCE", 4.1, true, true, true, true, 1);
```

## Deprecated Traps & Edge Cases (2026)
- Using NPCs where an actor suffices, wasting player slots.
- An NPC not spawned never appears.

## Verification
- Actor appears with the animation; NPC spawns and is queryable.
- Player slot count reflects the NPCs.
