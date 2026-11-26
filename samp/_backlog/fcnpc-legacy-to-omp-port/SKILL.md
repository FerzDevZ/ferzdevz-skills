---
name: fcnpc-legacy-to-omp-port
description: Port FCNPC code to open.mp natives.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, migration]
    category: samp
---

# FCNPC port

## When to Use
- A 0.3.7 gamemode depends on FCNPC.
- open.mp has built-in NPC support.

## 2026 Compatibility & Architecture Matrix
- FCNPC functions map to NPC_* equivalents; names and some signatures differ.
- NPCs created with the omp API are real player slots.

## Production Implementation
1. Inventory every FCNPC call and map it to the NPC_* API.
2. Replace callbacks with the omp NPC callbacks (OnNPCSpawn, OnNPCDeath, ...).
3. Retest pathing and combat behaviour.

```pawn
// FCNPC_Create -> NPC_Create, FCNPC_Spawn -> NPC_Spawn
```

## Deprecated Traps & Edge Cases (2026)
- Keeping FCNPC loaded alongside the native NPC API.
- Assuming identical spawn semantics.

## Verification
- No FCNPC include remains and NPC behaviour matches on a test server.
- Log shows NPC callbacks firing.
