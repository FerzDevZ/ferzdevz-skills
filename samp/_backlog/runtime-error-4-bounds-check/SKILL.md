---
name: runtime-error-4-bounds-check
description: Fix runtime error 4 with systematic bounds checks.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, crash]
    category: samp
---

# runtime error 4

## When to Use
- `Run time error 4: Array index out of bounds` appears in the log.
- An id from a packet indexes a fixed array.

## 2026 Compatibility & Architecture Matrix
- Pawn arrays are fixed at compile time; a negative or oversized index aborts the AMX.
- Pool ids from the network are untrusted input.

## Production Implementation
1. Reproduce with the same input and read the crashdetect line number.
2. Clamp with an explicit `if (id < 0 || id >= MAX) return;` before the index.
3. Add the check to a shared helper and reuse it everywhere.

```pawn
stock bool:ValidSlot(slot) { return slot >= 0 && slot < MAX_SLOTS; }
if (!ValidSlot(slot)) return SendClientMessage(playerid, -1, "Invalid slot");
```

## Deprecated Traps & Edge Cases (2026)
- Clamping with `%` hides the bug and writes the wrong row.
- Checking only the upper bound misses `-1` from a failed lookup.

## Verification
- The reproducing input now returns cleanly and logs the rejection.
- Grep shows every pool index guarded by the helper.
