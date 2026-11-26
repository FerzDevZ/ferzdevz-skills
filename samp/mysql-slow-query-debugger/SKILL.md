---
name: mysql-slow-query-debugger
description: Use when a gamemode query stalls or times out at load.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, mysql, performance, explain, indexing]
    category: samp
---

# Find the query that fills the pool, then make it cheap

"Threaded" does not mean "free": a query that takes two seconds still occupies a
connection, and R41-4's pool is two connections by default, so three slow saves
queue everything behind them. Blocking `mysql_query` is worse and stalls the whole
tick. The work is to name the query from server-side evidence, read its plan, add
the index that removes the scan, and keep the result under a budget you enforce in
Pawn.

## When to Use

- Saves or loads spike and the server hitches for a second or more.
- Queries time out under load and `mysql_unprocessed_queries` keeps growing.
- `EXPLAIN` reports `type: ALL` with thousands of rows for a lookup.
- A command that "should be instant" freezes every player for a moment.
- You need the exact query text and the gamemode call site that issued it.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Database | MySQL 8.4 LTS / 8.0 | `EXPLAIN ANALYZE` needs 8.0.18+ |
| Plugin | BlueG R41-4 | `mysql_tquery` async; `mysql_query` blocks the caller |
| Pool | `POOL_SIZE` (default 2) | slow queries queue; watch `mysql_unprocessed_queries` |
| Per-query timing | `cache_get_query_exec_time` | reads the last query's server time in the callback |
| Log sink | `log_output` = `FILE` or `TABLE` | `mysql.slow_log` stays empty unless `TABLE` is included |
| Tools | `mysqldumpslow`, `performance_schema` digests | aggregate by digest, never by raw text |

## Production Implementation

1. Turn the slow log on with a threshold that catches your pain, and route it to a
   table so you can query it without shelling into the host.

```sql
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 0.2;
SET GLOBAL log_output = 'TABLE';
SELECT COUNT(*) AS slow_rows FROM mysql.slow_log;
```

2. Aggregate by digest instead of reading query text: the digest collapses every
   literal into `?`, so one row is one query shape with real totals.

```sql
SELECT DIGEST_TEXT, COUNT_STAR, ROUND(SUM_TIMER_WAIT/1000000000, 1) AS total_ms,
       ROUND(AVG_TIMER_WAIT/1000000, 2) AS avg_ms,
       SUM_ROWS_EXAMINED, SUM_NO_INDEX_USED
FROM performance_schema.events_statements_summary_by_digest
WHERE SCHEMA_NAME = 'samp'
ORDER BY SUM_TIMER_WAIT DESC LIMIT 10;
```

3. Read the plan before changing anything. `rows` is the estimate that matters;
   `ALL` on a lookup table means a full scan.

```sql
EXPLAIN SELECT id, cash FROM player_stats WHERE player = 'p42';
```

```text
| type | possible_keys | key  | rows  | Extra       |
| ALL  | NULL          | NULL | 20000 | Using where |
```

4. Add the index concurrently, so writes keep flowing while it builds. A missing
   index on the write path is worse: the `UPDATE` scans and holds row locks longer.

```sql
ALTER TABLE player_stats ADD INDEX ps_player (player), ALGORITHM=INPLACE, LOCK=NONE;
EXPLAIN SELECT id, cash FROM player_stats WHERE player = 'p42';
```

```text
| type | possible_keys | key       | rows | Extra |
| ref  | ps_player     | ps_player |    1 | NULL  |
```

5. When the estimate lies (composite filters, skewed data), use `EXPLAIN ANALYZE`
   and read actual time and actual rows per node, not the cost number.

```sql
EXPLAIN ANALYZE SELECT id, cash FROM player_stats WHERE player = 'p42';
```

6. Instrument the gamemode so the next regression is visible without the DBA. Log
   the digest text and duration from inside the callback, and alert on backlog.

```pawn
forward OnStatsLoaded(playerid);

public OnStatsLoaded(playerid)
{
    new ms = cache_get_query_exec_time(MILLISECONDS);
    new text[192];
    cache_get_query_string(text, sizeof text);
    if (ms > 100) printf("[sql] %d ms %s", ms, text);
    if (mysql_unprocessed_queries(g_DB) > 8) print("[sql] pool backlog");
    return 1;
}
```

7. Kill the common shapes: `SELECT *` moves columns you never read, a function on
   an indexed column (`WHERE DATE(saved_at) = CURDATE()`) disables the index, and
   `LIMIT 50 OFFSET 9000` still walks 9050 rows. Use keyset pagination instead.

```sql
-- walks 9050 rows
SELECT id FROM player_stats ORDER BY id LIMIT 50 OFFSET 9000;
-- walks 50
SELECT id FROM player_stats WHERE id > 9000 ORDER BY id LIMIT 50;
```

8. Remove N+1: one query per inventory row or per online player is the usual cause
   of a pool backlog, and it is fixed by one `WHERE owner_id IN (...)` or one
   `INSERT ... VALUES (...),(...)` batch, not by a bigger pool.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Slow log stays empty | `long_query_time` still 10, or `log_output=FILE` and you query `mysql.slow_log` | lower the threshold, set `log_output='TABLE'` |
| Index added, `EXPLAIN` still shows `ALL` | column wrapped in a function, or type mismatch (`VARCHAR` column vs integer literal) | compare raw columns, cast the literal not the column |
| Query is fast alone, slow under load | it waits on a row lock, not on rows: `1205` after `innodb_lock_wait_timeout` | shorten the transaction, retry, check `SHOW ENGINE INNODB STATUS` |
| Server hitches even though queries are async | pool of 2 saturated by one 2-second query per player | index the query, batch it, raise `POOL_SIZE` only after |
| Freeze lasting one tick | blocking `mysql_query` called from a command/callback | convert to `mysql_tquery` with a callback |
| Every save is its own round trip | N+1 loop over players | one batch statement per tick |

## Verification

```bash
mysql -uroot -p"$PW" samp -e "
  EXPLAIN SELECT id, cash FROM player_stats WHERE player = 'p42'\G" \
  | grep -E '^ +type:|^ +rows:'
mysql -uroot -p"$PW" -e "
  SELECT SUM_ROWS_EXAMINED FROM performance_schema.events_statements_summary_by_digest
   WHERE DIGEST_TEXT LIKE '%player_stats%' AND DIGEST_TEXT LIKE 'SELECT%';"
```

- `grep` prints `type: ref` and `rows: 1` (was `type: ALL` / `rows: 20000`).
- After a day of traffic the digest's `SUM_ROWS_EXAMINED` for that shape is in the
  tens per call, and `SUM_NO_INDEX_USED` no longer grows.
- No entry for the shape in `mysql.slow_log` with `long_query_time = 0.2`.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/slow-query-log.html
- https://dev.mysql.com/doc/refman/8.4/en/explain.html
- https://dev.mysql.com/doc/refman/8.4/en/performance-schema-statement-summary-tables.html
