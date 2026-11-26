---
name: blueg-mysql-r41-threaded
description: Use BlueG MySQL R41-4 correctly and threaded.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql]
    category: samp
---

# BlueG R41-4

## When to Use
- The gamemode stalls on saves or queries.
- You need the modern threaded API on 0.3.7/open.mp.

## 2026 Compatibility & Architecture Matrix
- R41-4 provides `mysql_tquery` (threaded) and `mysql_query` (blocking).
- `mysql_format` builds the statement; never concatenate.

## Production Implementation
1. `mysql_connect` in `OnGameModeInit` and check the handle.
2. Wrap every query in `mysql_format` + `mysql_tquery` with a callback.
3. Read results from the cache inside the callback only.

```pawn
mysql_format(g_DB, query, sizeof query, "SELECT money FROM accounts WHERE id = %d", id);
mysql_tquery(g_DB, query, "OnAccountLoaded", "ii", playerid, id);
```

## Deprecated Traps & Edge Cases (2026)
- Using `mysql_query` in a hot path blocks the whole server.
- Reading the cache after the callback returned.

## Verification
- No blocking calls remain in the code (grep).
- Query latency stays flat under 100 players.
