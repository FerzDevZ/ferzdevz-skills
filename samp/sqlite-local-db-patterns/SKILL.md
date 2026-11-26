---
name: sqlite-local-db-patterns
description: Use when one node needs persistence without a DB daemon.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, database]
    category: samp
---

# SQLite for a single node

## When to Use

- A small or mid-size server needs persistence and you do not want to run MySQL next to it.
- Local state (cooldowns, market prices, last login) must survive a restart and fit in one file.
- You want a database you can copy, open with `sqlite3` and diff during an incident.
- Not for several servers or several worlds writing the same tables, and not on a network filesystem.

## Compatibility & Stack Matrix (2026)

| Item | Value | Notes |
| --- | --- | --- |
| Pawn access | core `db_*` natives | no plugin needed: `db_open`, `db_query`, `db_free_result` |
| File location | `/scriptfiles` | `db_open` takes a *name* inside scriptfiles, not an absolute path |
| Open flags | read/write + create by default | `SQLITE_OPEN_READWRITE | SQLITE_OPEN_CREATE` is the default for `db_open` |
| Journal mode | WAL | readers stop blocking the writer; same host only, no network filesystem |
| Backup | `VACUUM INTO` or `.backup` | a plain `cp` of a live WAL database is a torn copy |
| Error logging | `logging.log_sqlite`, `logging.log_sqlite_queries` | `config.json` keys; turn on while debugging |
| Leak counters | `db_debug_openfiles`, `db_debug_openresults` | open connections and unfreed result sets |

## Production Implementation

1. Put the file under `scriptfiles` and set the journal mode once from the CLI. The mode is stored in the
   file; `synchronous` is per connection, so set it in code too:

```bash
sqlite3 scriptfiles/economy.db "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"
sqlite3 scriptfiles/economy.db "PRAGMA journal_mode;"
```

2. Let the schema enforce invariants the script can forget, and keep the money and its timestamp in one
   row so a single statement stays atomic:

```sql
CREATE TABLE IF NOT EXISTS accounts (
  id         INTEGER PRIMARY KEY,
  name       TEXT    NOT NULL UNIQUE,
  money      INTEGER NOT NULL DEFAULT 0 CHECK (money >= 0),
  updated_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_accounts_updated ON accounts(updated_at);
```

3. Open once at start-up and close at exit; a failed open must stop startup instead of running with a null handle:

```pawn
new DB:gDB;

public OnGameModeInit()
{
    gDB = db_open("economy.db");
    if (!gDB)
    {
        print("economy.db did not open: check scriptfiles/ exists and is writable");
        return 0;
    }
    db_query(gDB, "PRAGMA busy_timeout = 5000");
    db_query(gDB, "PRAGMA foreign_keys = ON");
    return 1;
}

public OnGameModeExit()
{
    if (gDB) db_close(gDB);
    return 1;
}
```

4. Read with the named-field accessors and free every result. An unfreed result holds a read
   transaction open, which blocks checkpoints and grows the `-wal` file:

```pawn
stock GetMoney(const name[])
{
    new query[160], DBResult:res, money;
    format(query, sizeof(query), "SELECT money FROM accounts WHERE name = '%s'", name);
    res = db_query(gDB, query);
    if (!res) return 0;
    if (db_num_rows(res) > 0) money = db_get_field_assoc_int(res, "money");
    db_free_result(res);
    return money;
}
```

`name` must already be restricted to the charset allowed at registration (`A-Za-z0-9_`): `db_query` has
no prepared statements, so interpolation is the only option and the whitelist is the guard.

5. Batch writes. One transaction per flush, driven by a timer, never one write per tick:

```pawn
public OnEconomyFlush()
{
    if (!gDB) return 0;
    new query[192];
    db_query(gDB, "BEGIN IMMEDIATE");
    for (new i = 0; i < MAX_PLAYERS; i++)
    {
        if (!IsPlayerConnected(i)) continue;
        format(query, sizeof(query),
            "UPDATE accounts SET money = %d, updated_at = strftime('%%s','now') WHERE id = %d",
            gMoney[i], gAccountId[i]);
        db_query(gDB, query);
    }
    db_query(gDB, "COMMIT");
    return 1;
}
```

6. Back up with the SQLite tooling, not with `cp`: `VACUUM INTO` refuses to overwrite an existing file
   and checkpoints as it copies. Checkpoint the live file on shutdown so the `-wal` does not keep every
   change since the last restart:

```bash
sqlite3 scriptfiles/economy.db "PRAGMA wal_checkpoint(TRUNCATE);"
sqlite3 scriptfiles/economy.db "VACUUM INTO 'backups/economy-$(date +%F).db'"
sqlite3 "backups/economy-$(date +%F).db" "PRAGMA integrity_check;"
```

7. Watch the leak counters from a debug command instead of guessing. If `db_debug_openresults` climbs
   while nobody is querying, a `db_query` result is not being freed on some path.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `database is locked` under a flush | two connections writing, or no wait budget | one connection, `PRAGMA busy_timeout=5000` |
| `db_open` returns 0 | passed a path, or scriptfiles is not writable | pass `economy.db`, check directory ownership |
| Memory and `-wal` grow hour by hour | result sets never freed | `db_free_result` on every path, watch `db_debug_openresults` |
| Restored backup is missing recent rows or is corrupt | `cp` of a live WAL database | `VACUUM INTO` or `.backup`, verify with `integrity_check` |
| WAL files never shrink | a long-lived read result blocks checkpointing | free results, checkpoint on shutdown |
| Tick lasts 20 ms after the write feature ships | one `UPDATE` per player per tick | batch in a timer with one transaction |
| A name with an apostrophe returns no rows | interpolated text, not escaped | whitelist the name charset at registration |

## Verification

```bash
sqlite3 scriptfiles/economy.db "PRAGMA journal_mode; PRAGMA integrity_check;"
sqlite3 scriptfiles/economy.db "SELECT COUNT(*) || ' rows, min money ' || MIN(money) FROM accounts;"
sqlite3 scriptfiles/economy.db ".tables"
```

Expected output — WAL is active, the file is consistent, and the table survived a restart:

```text
wal
ok
142 rows, min money 0
accounts
```

Then prove the backup path end to end: `sqlite3 scriptfiles/economy.db "VACUUM INTO '/tmp/verify.db'" && sqlite3 /tmp/verify.db "SELECT COUNT(*) FROM accounts;"` returns the same row count (`142`).

## Sources (2026)

- https://open.mp/docs/scripting/functions/db_open
- https://open.mp/docs/scripting/functions/db_query
- https://sqlite.org/wal.html
- https://sqlite.org/lang_vacuum.html
