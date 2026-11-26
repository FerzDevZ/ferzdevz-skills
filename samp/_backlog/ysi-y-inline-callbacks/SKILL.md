---
name: ysi-y-inline-callbacks
description: Use y_inline for callback-style APIs without globals.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# y_inline

## When to Use
- A timer or dialog needs to carry per-player state without a global array.
- You want a closure-like pattern in Pawn.

## 2026 Compatibility & Architecture Matrix
- `y_inline` builds a generated function per call site.
- Works on both targets; no plugin required.

## Production Implementation
1. Include `<YSI_Coding/y_inline>` and pass `using inline` parameters.
2. Keep inline bodies short; heavy logic goes to a normal function.
3. Verify generated names do not collide across modules.

```pawn
#include <YSI_Coding/y_inline>
SetTimerEx("OnPulse", 1000, false, "ii", playerid, _:using inline (playerid) { });
```

## Deprecated Traps & Edge Cases (2026)
- Inline blocks that capture large arrays increase AMX size.
- Two identical inline bodies in one scope can collide; name the wrapper.

## Verification
- Compiles with 0 warnings and the callback runs once.
- AMX size delta is recorded per feature.
