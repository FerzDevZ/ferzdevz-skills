---
name: database-schema-migration
description: Use when a schema change must ship without dropping players.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, mysql, ddl, migration, deployment]
    category: samp
---

# Ship schema changes forward, numbered and reserved

A gamemode is deployed many times against a database that outlives it. The
failure that takes the server down is never "the migration was slow"; it is "the
old Pawn code met a new column" or "two instances applied the same file". Treat
migrations as numbered, forward-only files that reserve their version row before
touching a table, and expand the schema in two releases instead of one.

## When to Use

- Two servers or a web UCP share one database and one schema.
- You need to rename, split or drop a column without breaking the running gamemode.
- A fresh install and a two-year-old database have drifted apart.
- A deploy was interrupted halfway and you do not know what applied.
- You want an auditable answer to "which migration ran, when, on which host".

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| Database | MySQL 8.4 LTS / 8.0 | `ALGORITHM=INSTANT` is the default for `ADD COLUMN` in 8.4 |
| Alternative | MariaDB 10.11 | supports `INSTANT` for a narrower set of operations; check per statement |
| Plugin | BlueG R41-4 | run DDL from the deploy script, not a player callback |
| Driver | `mysql` CLI in deploy/CI | one connection per invocation, so no lock survives a loop |
| Version table | `schema_version` | primary key on `version` makes the reservation atomic |
| Big tables | `gh-ost` or `pt-online-schema-change` | when `INPLACE` still rebuilds and the table is hot |

## Production Implementation

1. One file per change, numbered, never edited after it ran. The filename carries
   the version the table records.

```bash
db/migrations/0004_add_account_flags.sql
db/migrations/0005_backfill_flags.sql
```

2. Keep the version table small and let the primary key do the concurrency work:
   reserving a row is atomic, so only one runner can own a version.

```sql
CREATE TABLE IF NOT EXISTS schema_version (
  version    INT UNSIGNED NOT NULL PRIMARY KEY,
  name       VARCHAR(64)  NOT NULL,
  status     ENUM('running','applied') NOT NULL DEFAULT 'running',
  checksum   CHAR(64)     NOT NULL,
  applied_at TIMESTAMP    NULL DEFAULT NULL
) ENGINE=InnoDB;
```

3. Every migration file starts by reserving its own version. `ROW_COUNT()` is 1
   only for the runner that inserted the row; the loser proceeds and fails loudly
   on `1060 duplicate column` instead of applying twice.

```sql
INSERT INTO schema_version (version, name, checksum)
  VALUES (4, 'add_account_flags',
          SHA2('ALTER TABLE accounts ADD COLUMN flags INT UNSIGNED NOT NULL DEFAULT 0', 256))
  ON DUPLICATE KEY UPDATE version = version;
```

4. Then the DDL, then the status update in the same file. If the server dies
   between them, the row stays `running` and the next deploy stops on it.

```sql
ALTER TABLE accounts ADD COLUMN flags INT UNSIGNED NOT NULL DEFAULT 0, ALGORITHM=INSTANT;
UPDATE schema_version SET status = 'applied', applied_at = NOW()
  WHERE version = 4 AND status = 'running';
```

5. The runner is a loop with no cleverness: skip applied versions, run the rest,
   stop on the first error. It runs from the deploy step, never from
   `OnGameModeInit` on every instance.

```bash
set -euo pipefail
# credentials live in ~/.my.cnf, never in this script
DB=${DB:-samp}
for f in db/migrations/*.sql; do
  v=$(basename "$f" .sql | cut -d_ -f1 | sed 's/^0*//')
  if [ "$(mysql "$DB" -N -e "SELECT COUNT(*) FROM schema_version WHERE version=$v")" = "0" ]; then
    mysql "$DB" < "$f"
  fi
done
```

6. Never create a client lock with `GET_LOCK` from a bash loop: the lock belongs
   to the connection that took it and dies with that `mysql` process. It is the
   right tool only when one process holds one connection for the whole run.

```sql
SELECT GET_LOCK('samp.schema', 10) AS got_lock;   -- 1 = held, 0 = timed out
```

7. Rename and drop in two releases (expand, then contract). Release A adds the new
   column and writes both; release B reads only the new one; release C drops the
   old one after no deployed build reads it.

```sql
-- release A: add, dual-write from Pawn, then backfill in chunks
ALTER TABLE accounts ADD COLUMN bank_cents BIGINT NOT NULL DEFAULT 0, ALGORITHM=INSTANT;
UPDATE accounts SET bank_cents = bank * 100 WHERE bank_cents = 0 AND bank <> 0 LIMIT 5000;
```

8. Pick the least invasive algorithm explicitly, so a future MySQL default change
   cannot silently rebuild a hot table during peak hours.

```sql
ALTER TABLE accounts ADD INDEX accounts_name_idx (name), ALGORITHM=INPLACE, LOCK=NONE;
```

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Unknown column` in a gamemode that was fine yesterday | code deployed before the DDL, or DDL rolled back | apply schema first, then code; expand/contract for renames |
| Migration applied twice and the second run errors | no reservation, two instances booted together | reserve the version row first; let the loser fail |
| Deploy stuck on a `running` row | crash between DDL and status update | inspect the table, finish by hand, then set `applied_at` |
| `ALTER TABLE` freezes the server for minutes | implicit table copy (`ALGORITHM=COPY`) | `ALGORITHM=INSTANT` for column adds, `INPLACE, LOCK=NONE` for indexes |
| `ERROR 4092 ... row size crosses max permissible` | too many `INSTANT` column adds on one table | fall back to `ALGORITHM=INPLACE` in a maintenance window |
| Fresh install and production schemas differ | migrations edited after being applied | checksum in `schema_version`, compare dumps in CI |

## Verification

```bash
mysqldump --no-data --skip-comments samp        > /tmp/fresh.sql
mysqldump --no-data --skip-comments samp_upgraded > /tmp/upgraded.sql
diff /tmp/fresh.sql /tmp/upgraded.sql && echo "schemas identical"
mysql samp -e "SELECT version, name, status FROM schema_version ORDER BY version;"
```

- `schemas identical` with an empty diff: a fresh install and an upgraded database
  produce the same `CREATE TABLE` output.
- `schema_version` lists one row per migration, every one `applied`, none `running`.
- Re-running the deploy script changes nothing and prints no `mysql` errors.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/innodb-online-ddl-operations.html
- https://dev.mysql.com/doc/refman/8.4/en/locking-functions.html
- https://dev.mysql.com/doc/refman/8.4/en/alter-table.html
