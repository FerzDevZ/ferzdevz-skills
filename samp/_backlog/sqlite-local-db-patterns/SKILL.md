---
name: sqlite-local-db-patterns
description: Use SQLite for single-instance local data.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, database]
    category: samp
---

# SQLite patterns

## When to Use
- A small server needs persistence without a DB service.
- You need fast local caches that survive restart.

## 2026 Compatibility & Architecture Matrix
- SQLite is single-writer; long transactions block other writes.
- Pawn access is through a plugin/component, not native SQL.

## Production Implementation
1. Keep the DB file on local disk, not a network share.
2. Batch writes in a transaction and keep them short.
3. Back up by copying the file while no writer is active.

```bash
sqlite3 server.db ".backup backup.db"
```

## Deprecated Traps & Edge Cases (2026)
- Using SQLite for a multi-server shard.
- A write per tick instead of a batched flush.

## Verification
- Write latency stays under the tick budget.
- Restore from the copy opens and counts rows.
