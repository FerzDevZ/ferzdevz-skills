---
name: tablist-headers-formatting
description: Format tablist headers with per-player data.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui]
    category: samp
---

# tablist header

## When to Use
- Tablist is static or wrong for some players.
- Long lists of names break formatting.

## 2026 Compatibility & Architecture Matrix
- `SetPlayerChatBubble` is not a tablist; use the tablist natives/`omp` API for headers.
- Keep the update on a timer, not per tick.

## Production Implementation
1. Build the header string with server state.
2. Refresh every second and only when the value changed.
3. Cap names and counts to the string buffer.

```pawn
new s[256]; format(s, sizeof s, "Online: %d", GetPlayerCount());
```

## Deprecated Traps & Edge Cases (2026)
- Per-tick tablist updates.
- Unbounded name concatenation.

## Verification
- Header updates once per second and stays within buffer limits.
- No flicker under load.
