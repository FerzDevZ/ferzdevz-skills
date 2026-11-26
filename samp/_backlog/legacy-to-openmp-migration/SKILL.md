---
name: legacy-to-openmp-migration
description: Migrate a 0.3.7 gamemode to open.mp safely.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, migration]
    category: samp
---

# 0.3.7 to open.mp migration

## When to Use
- A 0.3.7 gamemode must run on open.mp v1.6.
- Includes, callbacks or natives differ between targets.

## 2026 Compatibility & Architecture Matrix
- Keep `network.allow_037_clients` true while both client generations exist.
- `<open.mp>`/omp-stdlib supersedes `<a_samp>`; `fixes.inc` is unnecessary on open.mp.
- `OnPlayerDeath` weapon parameter is tagged `WEAPON:` on open.mp.

## Production Implementation
1. Switch includes to omp-stdlib and compile with 0 warnings.
2. Replace removed/renamed natives listed by the compiler, one batch at a time.
3. Run the same player flow on both targets and diff the log.

```pawn
#include <open.mp>
public OnPlayerDeath(playerid, killerid, WEAPON:reason) { return 1; }
```

## Deprecated Traps & Edge Cases (2026)
- Do not keep `fixes.inc` on open.mp: it re-defines callbacks the server already fixes.
- `GetPlayerPoolSize` triggers warning 234 on open.mp; track players with foreach.

## Verification
- Compile both targets with 0 warnings and compare the first 100 log lines.
- A test client connects, spawns and dies without a runtime error.
