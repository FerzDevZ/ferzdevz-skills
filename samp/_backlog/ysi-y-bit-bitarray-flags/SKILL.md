---
name: ysi-y-bit-bitarray-flags
description: Store per-player flags in y_bit bit arrays.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# y_bit flags

## When to Use
- Dozens of booleans per player bloat the script.
- Flag checks spread across modules.

## 2026 Compatibility & Architecture Matrix
- `BitArray` packs flags into one cell per player; `y_bit` is part of YSI 5.x.
- Flags are indexes, not bit shifts, in the YSI API.

## Production Implementation
1. Define an enum of flag indexes once.
2. Set/clear/read through the BitArray in the owning module.
3. Log flag transitions for admin-relevant flags.

```pawn
#include <YSI_Coding/y_bit>
new BitArray:g_Flags<MAX_PLAYERS>;
SetBitArray(g_Flags, playerid, FLAG_JAILED, true);
```

## Deprecated Traps & Edge Cases (2026)
- Mixing raw bit masks and BitArray indexes.
- Forgetting to clear flags on connect, inheriting the previous session.

## Verification
- Flags survive a reconnect test only when the design says so.
- Memory per player is documented.
