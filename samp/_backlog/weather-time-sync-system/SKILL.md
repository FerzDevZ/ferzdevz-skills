---
name: weather-time-sync-system
description: Sync weather and time across worlds.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, world]
    category: samp
---

# weather/time sync

## When to Use
- Weather differs per player or resets on respawn.
- Time jumps after a restart.

## 2026 Compatibility & Architecture Matrix
- `SetWeather`/`SetWorldTime` are global; per-player requires `SetPlayerWeather`/`SetPlayerTime`.
- Sync on spawn and periodically.

## Production Implementation
1. Keep a server clock and broadcast changes.
2. Apply per player on spawn and on change.
3. Persist the current weather/time in the DB.

```pawn
SetPlayerTime(playerid, hour, minute); SetPlayerWeather(playerid, weatherid);
```

## Deprecated Traps & Edge Cases (2026)
- Setting world time per player expecting persistence.
- Reapplying weather every tick.

## Verification
- All players report the same time after spawn.
- A restart restores the persisted values.
