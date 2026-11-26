---
name: postgres-query-and-index-tuning
description: Use when a Postgres query is slow or times out at scale.
version: "2026.1.0"
metadata:
  hermes:
    tags: [postgresql, indexing, explain, query-tuning, n+1, pooling]
    category: web-dev
---

# Tune Postgres from EXPLAIN evidence, not index folklore

Slow queries are diagnosed from a plan with real parameters, buffer counts and row
estimates. Adding an index because a column appears in `WHERE` is how teams end up
with twelve unused indexes and a write-amplified table. Measure, then change one thing.

## When to Use

- A query or endpoint exceeds its latency budget as the table grows.
- `pg_stat_statements` shows one normalized query dominating total execution time.
- A new index did not change the plan, or writes got slower after indexing.
- The app issues thousands of near-identical queries per request (N+1).
- Skip for a table under a few thousand rows: a sequential scan is already correct.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Notes |
| --- | --- | --- |
| PostgreSQL | 16-19 (19 is current) | 19 prints `Index Searches` per plan node in `EXPLAIN ANALYZE` |
| pg_stat_statements | contrib extension | Normalized queries with calls, rows, mean and total time |
| Index types | B-tree default; GIN, BRIN, hash, partial | Multicolumn B-tree allows up to 32 columns including `INCLUDE` |
| Pooling | PgBouncer 1.24+ in transaction mode | Keep pool size below the Postgres connection budget |
| Driver | node-postgres 8.23 or psycopg 3 | Pool `max` must account for every app instance |
| Maintenance | autovacuum + manual `ANALYZE` | Statistics decide the plan; stale stats beat any index |

## Production Implementation

1. Rank queries by total time, not by how slow one run felt.

```sql
select calls,
       round(total_exec_time::numeric, 1) as total_ms,
       round(mean_exec_time::numeric, 2) as mean_ms,
       rows,
       left(query, 90) as query
from pg_stat_statements
order by total_exec_time desc
limit 20;
```

2. Capture the plan with real parameters, buffers and settings.

```sql
begin;
explain (analyze, buffers, verbose, settings)
update orders set status = 'shipped' where id = 42;
rollback;
```

`ANALYZE` executes the statement, so wrap DML in a transaction you roll back. Read
estimated `rows` against `actual rows`, `loops`, `Buffers: shared hit/read`, the sort
method, and `Heap Fetches` before deciding anything.

3. Interpret the plan with this map.

| Signal | Meaning | Action |
| --- | --- | --- |
| `rows=1 ... actual rows=50000` | Stale or correlated statistics | `ANALYZE`, then `CREATE STATISTICS ... (dependencies)` |
| High `shared read`, low `hit` | Cold cache or too many pages touched | Narrower index, more selective predicate |
| `Sort Method: external merge` | Sort spilled to disk | Raise `work_mem` for the session, or index the sort order |
| `Seq Scan` with a filter removing most rows | No usable index | Composite index matching the predicate |
| High `Heap Fetches` on an index-only scan | Visibility map is stale | `VACUUM` the table |
| `loops=10000` on an inner node | N+1 shape inside one SQL statement | Rewrite as a set-based join |

4. Design composite indexes equality-first, range last, and cover the select list.

```sql
create index concurrently orders_customer_created_idx
  on orders (customer_id, created_at desc)
  include (total_cents)
  where status <> 'cancelled';
```

The leading columns must match equality predicates; the first non-equality column ends
the usable prefix. A partial predicate only applies when the query implies it, and
`CONCURRENTLY` cannot run inside a transaction block.

5. Prove the index is used, and find the dead weight.

```sql
select indexrelname,
       idx_scan,
       pg_size_pretty(pg_relation_size(indexrelid)) as size
from pg_stat_user_indexes
where relname = 'orders'
order by pg_relation_size(indexrelid) desc;
```

`idx_scan = 0` after a full workload cycle means the index costs writes for nothing.
Drop it concurrently with `drop index concurrently`, after checking it is not a
constraint backing index.

6. Detect N+1 from statement statistics rather than reading every ORM call.

```sql
select calls,
       rows,
       round(rows::numeric / greatest(calls, 1), 2) as rows_per_call,
       left(query, 80) as query
from pg_stat_statements
where calls > 10000
order by calls desc
limit 20;
```

One statement with tens of thousands of calls and ~1 row per call is an N+1. Fix it in
the data layer with a join, `IN (...)` batching, or a dataloader; caching the symptom
leaves the query count intact.

7. Size the pool from measured concurrency, not from a copied number.

```sql
select state, wait_event_type, count(*)
from pg_stat_activity
where backend_type = 'client backend'
group by 1, 2
order by 3 desc;
```

Keep the sum of all pools below `max_connections - superuser_reserved_connections`.
Start near 2x vCPU and grow only while active sessions show real CPU load; a `Client`
wait means the database is idle waiting on the app, and `idle in transaction` is a bug.

8. Watch the build instead of guessing whether it is safe.

```sql
select phase, blocks_done, blocks_total
from pg_stat_progress_create_index;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Seq Scan on a large table filtering 2% of rows | No index, or a non-sargable predicate like `date(created_at) = ...` | Add a composite index; rewrite to a half-open timestamp range |
| Index exists but the planner ignores it | Predicate skips the leading column, or a type mismatch forces a cast on the column | Reorder columns; cast the parameter, never the indexed column |
| Estimate 1 row, actual 80k | Stale statistics or correlated columns | `ANALYZE`, then `CREATE STATISTICS ... (dependencies)` and re-check |
| Fast in psql, slow in the app | Generic prepared plan, or different role/session settings | Compare with the app's parameters; `set plan_cache_mode = force_custom_plan` |
| p99 spikes while CPU is idle | Pool saturation: requests queue for a backend | Measure wait events, cap pools, add `statement_timeout` |
| `CREATE INDEX CONCURRENTLY` fails | Ran inside a transaction, or a unique index hit duplicates | Run outside a transaction; deduplicate, then `REINDEX CONCURRENTLY` |
| Table and index bloat after bulk updates | Autovacuum cannot keep pace | Lower `scale_factor`, raise cost limits, monitor `n_dead_tup` |

## Verification

- `psql "$DATABASE_URL" -c "explain (analyze, buffers) select * from orders where customer_id = 42 and status <> 'cancelled' and created_at > now() - interval '30 days';"` shows `Index Scan using orders_customer_created_idx` and `Buffers: shared hit=`.
- `psql "$DATABASE_URL" -c "select indexrelname, idx_scan from pg_stat_user_indexes where relname = 'orders';"` shows the new index with `idx_scan > 0` after the workload runs.
- `pgbench -n -c 32 -j 4 -T 60 -f bench.sql "$DATABASE_URL"` reports stable tps and no `connection ... failed` lines.
- `psql "$DATABASE_URL" -c "show max_connections;"` exceeds the sum of every app pool plus reserved slots.

## Sources (2026)

- https://www.postgresql.org/docs/current/using-explain.html
- https://www.postgresql.org/docs/current/indexes-multicolumn.html
- https://www.postgresql.org/docs/current/indexes-partial.html
