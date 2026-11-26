---
name: notification-toast-queue
description: Queue transient notifications without overlap.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui]
    category: samp
---

# toast queue

## When to Use
- Messages overwrite each other.
- A player misses important notices.

## 2026 Compatibility & Architecture Matrix
- Per-player queue with a timer that advances after the display time.
- Priority for errors over informational toasts.

## Production Implementation
1. Push to a ring buffer per player with a priority.
2. Display one at a time and advance on a timer.
3. Clear the queue on death and disconnect.

```pawn
enum E_TOAST { text[96], until };
new g_Toast[MAX_PLAYERS][4];
```

## Deprecated Traps & Edge Cases (2026)
- Showing a new toast before the previous timer ends.
- Unbounded queue growth.

## Verification
- Rapid events display in order without overlap.
- Queue length is capped.
