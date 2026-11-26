---
name: omp-built-in-npc-scripting
description: Use open.mp native NPCs instead of FCNPC.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, npc]
    category: samp
---

# open.mp NPC API

## When to Use
- You need bots but FCNPC is not maintained for open.mp.
- NPCs must be created and driven by the server.

## 2026 Compatibility & Architecture Matrix
- NPC API ships in omp-stdlib `omp_npc.inc`; `NPC_Create` added in open.mp v1.5.8.3079.
- Verified functions include NPC_Create, NPC_IsValid, NPC_Spawn, NPC_SetPos, NPC_SetWeapon, NPC_SetAmmo, NPC_Destroy.

## Production Implementation
1. Include the omp NPC header and create NPCs in `OnGameModeInit`.
2. Spawn, set position and inventory, and track ids.
3. Destroy on gamemode exit and free slots.

```pawn
new npcid = NPC_Create("ShopBot");
if (NPC_IsValid(npcid)) { NPC_Spawn(npcid); NPC_SetPos(npcid, x, y, z); }
```

## Deprecated Traps & Edge Cases (2026)
- Porting FCNPC calls one-to-one; the API differs.
- Assuming NPCs spawn automatically — call `NPC_Spawn`.

## Verification
- `NPC_IsValid` is true and the NPC appears in game.
- Player slot count accounts for the NPCs.
