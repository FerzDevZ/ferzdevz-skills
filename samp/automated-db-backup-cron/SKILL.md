---
name: automated-db-backup-cron
description: Use when a database backup has never been restored.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, mysql, mariadb, ops, backup, cron]
    category: samp
---

# A dump is not a backup until the restore ran on a scratch schema

Every gamemode row — accounts, vehicles, houses, bans — lives in one InnoDB
schema. A nightly `mysqldump` is cheap; the part that fails is the file that
looks fine, weighs 30 KB and restores nothing because the client could not
connect. Build the dump with failure detection, keep it off the game host, and
prove it by importing it into a throwaway database on the same schedule.

## When to Use

- The server has run for months and nobody has ever restored a dump.
- A migration, a disk replacement or a `DROP TABLE` needs a rollback point.
- Cron "works" but the newest file is a gzip of an error message.
- You need a stated RPO (how much data loss is acceptable) and RTO (time to restore).
- Not for schema changes themselves — pair with `database-schema-migration`.

## Compatibility & Stack Matrix (2026)

| Component | Version / variant | Note |
| --- | --- | --- |
| MySQL server | 8.4 LTS / 8.0 | `--set-gtid-purged=OFF` needed on GTID-enabled servers |
| MariaDB server | 10.11 / 11.4 | `mariadb-dump` is the binary; it rejects `--set-gtid-purged` |
| Client | `mysqldump` 8.4, `mysql` 8.4 | client should be >= server major version |
| Storage engine | InnoDB only | `--single-transaction` is a no-op for MyISAM and leaves it inconsistent |
| Scheduler | cron (or a systemd timer) | cron has a minimal PATH and no `$HOME` |
| Credentials | `--defaults-extra-file` | keeps the password out of `ps` output |
| Off-host copy | `rclone` / `restic` / S3 | same-disk backups die with the disk |

## Production Implementation

1. Put credentials in a root-only option file. `mysqldump db -p"$PW"` leaks the
   password to every local user through `ps`, and cron has no shell to expand `$PW`.

```ini
# /etc/samp/backup.cnf   (chmod 600, owner root)
[client]
user=backup
password=CHANGE_ME
host=127.0.0.1
```

2. Write one script that fails loudly. Without `pipefail`, a failed `mysqldump`
   still leaves a valid empty `.gz` and cron reports success.

```bash
#!/usr/bin/env bash
set -euo pipefail
CNF=/etc/samp/backup.cnf
DB=samp
DIR=/var/backups/samp
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
OUT="$DIR/${DB}-${STAMP}.sql.gz"

mkdir -p "$DIR"
mysqldump --defaults-extra-file="$CNF" \
  --single-transaction --quick --skip-lock-tables \
  --routines --triggers --events --hex-blob --no-tablespaces \
  --set-gtid-purged=OFF "$DB" | gzip -9 > "$OUT"

gzip -t "$OUT"                                   # truncation check
[ "$(stat -c %s "$OUT")" -gt 20480 ] || { echo "dump too small" >&2; exit 1; }
sha256sum "$OUT" > "$OUT.sha256"
```

3. Two flags carry most of the risk. `--single-transaction` gives a consistent
   snapshot without locking writers, which matters because the gamemode writes
   every few seconds; `--quick` streams rows instead of buffering a whole table
   in RAM. `--no-tablespaces` avoids the `PROCESS` privilege that a least-privilege
   backup user should not have.

4. Prune on a real retention policy, then copy off-host. A pruned file that never
   left the host is not a backup.

```bash
find "$DIR" -name 'samp-*.sql.gz' -mtime +28 -delete
rclone copy "$DIR" remote:samp-backups --include 'samp-*.sql.gz*' --max-age 26h
```

5. Restore drill: import into a scratch schema with the same client the game
   host has, then compare row counts against production. Run it weekly, not
   monthly — a backup format change is what usually breaks it.

```bash
set -euo pipefail
SRC=$(ls -1t /var/backups/samp/samp-*.sql.gz | head -1)
mysql --defaults-extra-file=/etc/samp/restore.cnf \
  -e "DROP DATABASE IF EXISTS samp_restore; CREATE DATABASE samp_restore;"
gunzip -c "$SRC" | mysql --defaults-extra-file=/etc/samp/restore.cnf samp_restore

for t in players vehicles houses; do
  a=$(mysql --defaults-extra-file=/etc/samp/backup.cnf -N -B -e "SELECT COUNT(*) FROM samp.$t")
  b=$(mysql --defaults-extra-file=/etc/samp/restore.cnf -N -B -e "SELECT COUNT(*) FROM samp_restore.$t")
  printf '%-10s live=%s restored=%s\n' "$t" "$a" "$b"
done
```

6. Alert on backup age, not on cron exit. A silent cron entry that stopped
   running three weeks ago looks identical to a healthy one.

```bash
newest=$(find /var/backups/samp -name 'samp-*.sql.gz' -printf '%T@\n' | sort -n | tail -1)
age_h=$(( ( $(date +%s) - ${newest%.*} ) / 3600 ))
[ "$age_h" -lt 26 ] || echo "CRITICAL backup age ${age_h}h" | logger -t samp-backup
```

7. For containers, dump from a host that has the client, not from the DB
   container's entrypoint: `docker exec omp-db mariadb-dump ...` works, but a
   container restart during the dump kills the stream mid-file while the file
   still exists.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `.gz` restores nothing, cron says OK | `mysqldump` failed and the pipe wrote an empty file | `set -o pipefail` plus a `gzip -t` and size guard |
| `ERROR 1045 Access denied` only under cron | option file path relative, or `localhost` resolves to the socket in the cron env | absolute `--defaults-extra-file`, `host=127.0.0.1` |
| `Unknown variable 'set-gtid-purged=OFF'` | MariaDB server with a MySQL-only flag | drop the flag (or branch on `mariadb-dump`) |
| Restored data is inconsistent across tables | MyISAM tables under `--single-transaction` | convert to InnoDB, or accept `--lock-tables` downtime |
| Dump takes minutes and stalls saves | no consistent snapshot, so each table needs a lock | `--single-transaction --quick` together, then check pool backlog |
| Restore is 10x slower than the dump | no `--quick`, or one giant extended `INSERT` | add `--extended-insert --quick`, raise `max_allowed_packet` on the scratch server |
| Every nightly file is identical in size for weeks | cron stopped, file is a leftover | the age alert above, plus `sha256sum -c` on the newest pair |

## Verification

```bash
set -euo pipefail
/usr/local/bin/samp-db-backup.sh
NEW=$(ls -1t /var/backups/samp/samp-*.sql.gz | head -1)
gzip -t "$NEW"; echo "gzip ok $(basename "$NEW")"
gunzip -c "$NEW" | mysql --defaults-extra-file=/etc/samp/restore.cnf samp_restore
mysql --defaults-extra-file=/etc/samp/restore.cnf -N -B \
  -e "SELECT COUNT(*) FROM samp_restore.players;"
```

- `gzip -t` prints nothing and exits 0; any output means a truncated dump.
- The `gzip ok samp-20260101T030000Z.sql.gz` line names the file just written.
- The final count matches the live `players` count exactly (for example both
  print `14823`); a `0` means the dump was schema without data.
- `logger`-tagged output from step 6 stays empty: no `CRITICAL backup age` line.

## Sources (2026)

- https://dev.mysql.com/doc/refman/8.4/en/mysqldump.html
- https://dev.mysql.com/doc/refman/8.4/en/backup-and-recovery.html
- https://dev.mysql.com/doc/refman/8.4/en/mysql.html
