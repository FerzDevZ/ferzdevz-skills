---
name: multi-world-instance-sharding
description: Split players across worlds or instances.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, scaling]
    category: samp
---

# sharding

## When to Use
- One server is full or economies must be isolated.
- Players must not see other instances.

## 2026 Compatibility & Architecture Matrix
- Virtual worlds isolate visibility; separate servers isolate state.
- Sharding requires a shared account/economy contract.

## Production Implementation
1. Assign a world per instance and route teleports explicitly.
2. Namespace rows per shard where needed.
3. Measure cross-shard consistency.

```pawn
SetPlayerVirtualWorld(playerid, g_ShardWorld);
```

## Deprecated Traps & Edge Cases (2026)
- Using virtual worlds as data isolation.
- Two shards writing one row without locking.

## Verification
- Players in different shards never see each other; account data stays consistent.
