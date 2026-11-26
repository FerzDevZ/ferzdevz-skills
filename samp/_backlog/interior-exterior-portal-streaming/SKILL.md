---
name: interior-exterior-portal-streaming
description: Stream interiors and exteriors without seams.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# portal streaming

## When to Use
- Player sees a black void during a door transition.
- Objects pop in after arrival.

## 2026 Compatibility & Architecture Matrix
- Teleport + `Streamer_UpdateEx` + short freeze is the reliable sequence.
- World/interior change must precede the streamer update.

## Production Implementation
1. Freeze, set world/interior, teleport, update streamer, unfreeze.
2. Preload the destination interior shell at server start.
3. Log the transition for fall-through reports.

```pawn
TogglePlayerControllable(playerid, false);
SetPlayerPos(playerid, x, y, z); Streamer_UpdateEx(playerid, x, y, z);
TogglePlayerControllable(playerid, true);
```

## Deprecated Traps & Edge Cases (2026)
- Teleporting before setting the interior.
- Unfreezing before the streamer finishes.

## Verification
- No void frame on entry; no fall-through in 20 transitions.
