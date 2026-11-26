---
name: blueg-mysql-r41-threaded
description: Use when saves hitch the tick or callbacks read stale rows.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql, async, r41]
    category: samp
---

# Keep every query async and touch the cache only inside its callback

R41-4 offers two entry points that look similar and behave differently: `mysql_tquery`
runs the statement on a worker thread and queues the callback onto the main thread, while
`mysql_pquery` runs the callback on the worker thread too, where no native is safe to
call. The other half of the topic is ownership: a `Cache` belongs to the callback that
received it — read it there, copy what you need, then let it go.

## When to Use

- Saves or loads spike and the server hitches for a second or more.
- A callback reads a row that another query already overwrote.
- You are porting R39 code and `cache_get_field_content_int` no longer compiles.
- The query backlog grows while the server reports itself idle.
- A `mysql_pquery` callback crashes the moment it calls a native.

## Compatibility & Stack Matrix (2026)

| Component | 2026 baseline | Note |
| --- | --- | --- |
| Plugin | BlueG MySQL R41-4, `#include <a_mysql>` | `mysql_tquery`, `mysql_pquery`, `mysql_query` |
| Database | MySQL 8.4 LTS / MariaDB 10.11 | `utf8mb4` for names and chat |
| `mysql_tquery` callback | main thread | natives, player state and timers are safe |
| `mysql_pquery` callback | worker thread | no natives; copy values into globals only |
| Pool | `2 + POOL_SIZE` direct connections per handle | default `POOL_SIZE` is 2 |
| Cache API | `cache_get_row_count`, `cache_get_value_name_int` | R41-4 removed `cache_get_field_content*` |
| Logging | `mysql_log` is a deprecation stub in R41-4 | log levels live in `log-config.yml` |

## Production Implementation

1. Connect once, with options, and fail loudly. The handle is a tagged value, not a bool,
   so compare against `MYSQL_INVALID_HANDLE`:

```pawn
#include <openmp>
#include <a_mysql>

new MySQL:gDB = MYSQL_INVALID_HANDLE;

stock DBInit()
{
    new MySQLOpt:opt = mysql_init_options();
    mysql_set_option(opt, POOL_SIZE, 6);        // 8 direct connections per handle
    mysql_set_option(opt, AUTO_RECONNECT, true);

    gDB = mysql_connect("127.0.0.1", "samp", "samp", "samp", opt);
    if (gDB == MYSQL_INVALID_HANDLE)
    {
        printf("[db] connect failed, errno %d", mysql_errno());
        return 0;
    }
    return 1;
}
```

2. Never assemble SQL with `format`. `mysql_format` renders numbers and
   `mysql_escape_string(name, escaped, sizeof escaped, gDB)` escapes text in the
   connection's charset first; mixing the two is how a player name with a quote becomes a
   syntax error at 3 a.m. - then `"UPDATE accounts SET name = '%s' WHERE id = %d"`.

3. Pass arguments through the format string, not by concatenating them into the SQL. The
   two `i` specifiers match the two trailing callback arguments:

```pawn
forward OnAccountLoaded(playerid, accountid);

stock DBLoadAccount(playerid, accountid)
{
    new query[160];
    mysql_format(gDB, query, sizeof query,
        "SELECT cash, bank FROM accounts WHERE id = %d LIMIT 1", accountid);
    mysql_tquery(gDB, query, "OnAccountLoaded", "ii", playerid, accountid);
    return 1;
}

public OnAccountLoaded(playerid, accountid)
{
    if (!IsPlayerConnected(playerid)) return 0;      // disconnected mid-query
    if (accountid <= 0) return 0;

    new rows;
    cache_get_row_count(rows);
    if (rows == 0) { SendClientMessage(playerid, 0xFF4444FF, "Account missing."); return 0; }

    new cash, bank;
    cache_get_value_name_int(0, "cash", cash);
    cache_get_value_name_int(0, "bank", bank);
    gCash[playerid] = cash;
    gBank[playerid] = bank;
    return 1;
}
```

4. R41-4 ships `cache_get_value_name_int`, `cache_get_value_name_float`,
   `cache_get_value_index` and the `cache_num_rows()` stock. It has no
   `cache_get_field_content_int` at all, so a pasted R39 block fails at compile time with
   "function not found", never at runtime.

5. Batch the write path. One statement per player per event saturates a pool of eight long
   before 100 players: build one multi-row `INSERT ... VALUES (...),(...)` per tick for
   anything that can wait a tick, and keep single-row writes for durable events only.

```pawn
stock DBSaveBatch(const ids[], count)
{
    new query[2048], piece[96];
    new len = format(query, sizeof query, "INSERT INTO snapshots (account_id, cash) VALUES ");
    for (new i = 0; i < count && len < 1800; i++)
    {
        format(piece, sizeof piece, "%s(%d, %d)", i ? "," : "", ids[i], gCash[i]);
        strcat(query, piece, sizeof query);
    }
    mysql_tquery(gDB, query, "", "");
}
```

6. Route every failure into one place. The plugin forwards its own errors, so overriding
   `OnQueryError(errorid, error[], callback[], query[], MySQL:handle)` and printing all
   five fields keeps syntax errors next to the callback that produced them.

7. Keep `mysql_query` for boot-time schema checks only; inside a callback it blocks the
   whole tick and a saturated pool queues everyone behind it. While tuning, print
   `mysql_stat` on a 60-second timer — its question rate and slow-query counter say when a
   batch job costs more than it returns.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Every player hitches for a moment on save | `mysql_query` called from a callback | convert to `mysql_tquery` with a callback |
| Wrong player's money inside a callback | one shared cache read after a second query ran | read rows in the callback that received them |
| `function not found: cache_get_field_content_int` | R39 name removed in R41-4 | use `cache_get_value_name_int` |
| Crash inside a `mysql_pquery` callback | natives called on the worker thread | use `mysql_tquery`, or only touch globals |
| Queries queue while the database looks idle | pool saturated by long statements | batch, index, then raise `POOL_SIZE` |
| `mysql_log(LOG_ERROR)` prints nothing | deprecation stub in R41-4 | configure `log-config.yml` |
| Rows written for a player who already left | callback ran after disconnect | `IsPlayerConnected` as the first line |

## Verification

No blocking call may survive outside boot code, and no query may be built with `format`:

```bash
grep -rnE "mysql_query\(|format\(query, .*\"(SELECT|INSERT|UPDATE)" gamemodes/ ; echo "exit=$?"
```

Expected: no output lines, then `exit=1`. Any hit is a blocking query or an unescaped
statement. Runtime heartbeat, read from the `mysql_stat` line:

```text
[db] Uptime: 3600  Threads: 8  Questions: 41230  Slow queries: 0  QPS: 11
```

`Slow queries` stays 0, and `Questions` scales with player actions rather than ticks.

## Sources (2026)

- https://github.com/pBlueG/SA-MP-MySQL — plugin repository; `2 + pool_size` connections per handle, `mysql_static.so` for static linking.
- https://github.com/pBlueG/SA-MP-MySQL/releases/tag/R41-4 — the release this skill targets.
- https://raw.githubusercontent.com/pBlueG/SA-MP-MySQL/R41-4/a_mysql.inc.in — the real include: `mysql_tquery`/`mysql_pquery` signatures, `POOL_SIZE`, `cache_get_value_name_*`.
