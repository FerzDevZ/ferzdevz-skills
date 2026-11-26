---
name: ysi-y-iterate-foreach
description: Iterate players and vehicles with foreach.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# foreach

## When to Use
- `for (new i = 0; i < MAX_PLAYERS; i++)` scans 1000 slots.
- Loops must be correct at 200 players.

## 2026 Compatibility & Architecture Matrix
- `foreach (new i : Player)` iterates only connected players; `PlayerPool` is the 2026-safe pool name.
- `GetPlayerPoolSize` is warning 234 on open.mp.

## Production Implementation
1. Add `#include <YSI_Data/y_iterate>` and use `foreach` for every player loop.
2. Use `Vehicle`/`Object` iterators where the pool is known.
3. Remove manual `IsPlayerConnected` from the loop body.

```pawn
#include <YSI_Data/y_iterate>
foreach (new i : Player) { SendClientMessage(i, -1, "tick"); }
```

## Deprecated Traps & Edge Cases (2026)
- Iterating `MAX_PLAYERS` and calling natives for empty slots wastes CPU.
- A nested foreach over the same pool mutates it; collect first.

## Verification
- Loop body executes exactly the connected count.
- CPU at 200 players drops versus the old loop.
