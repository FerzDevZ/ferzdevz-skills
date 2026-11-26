---
name: backup-recovery-disaster-plan
description: Use when a host loss must be restored in minutes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops, mysql, backup]
    category: samp
---

# Restore a server from backups with a rehearsed runbook

A backup that has never been restored is a hypothesis. The plan is three numbers (RPO, RTO, drill
date), one off-host location, and a command list a second person can run on a host that is not the
old one. Everything below assumes open.mp with a MariaDB schema named `server`.

## When to Use

- The host, its disk or the provider is gone and the account database existed on that host only.
- A bad migration or a `DROP TABLE` needs a point-in-time restore, not a copy of last night.
- Two people disagree about what "restored" means and nobody has run the steps end to end.
- You cannot state how much data a failure costs (RPO) or how long recovery takes (RTO).
- Not for ordinary schema changes; that is `database-schema-migration`.

## Compatibility & Stack Matrix (2026)

| Asset | RPO | RTO | Mechanism | Proof of a working copy |
| --- | --- | --- | --- | --- |
| MariaDB `server` schema | 5 min | 25 min | nightly `mariadb-dump` + binlog archived every 5 min | drill restores to a binlog coordinate |
| `scriptfiles/` (houses, interiors, uploads) | 1 h | 8 min | `restic` snapshot on the hour | `restic check --read-data-subset=5%` |
| `config.json`, `pawn.json`, gamemode sources | 0 | 2 min | git tag per release, pushed to origin | tag resolves on a clean clone |
| open.mp runtime + plugins | n/a | 10 min | release tarball pinned by URL and sha256 | checksum matches the manifest |
| Whole service | 5 min | 45 min | 25 + 8 + 2 + 10, in order | drill measured under 2700 s |

Read the table as a floor. A 45-minute RTO only holds if the last drill measured 2700 seconds or
less on a scratch host; a 5-minute RPO only holds while the binlog archive is off-host and covers
seven days, otherwise the promise dies on day two.

## Production Implementation

1. Dump with a consistent snapshot and record the binlog position in the same file, so point-in-time
   recovery is reachable later without guessing:

```bash
install -d -m 0750 /srv/backup
ts=$(date -u +%Y%m%dT%H%MZ)
mariadb-dump --single-transaction --quick --routines --triggers --events \
  --source-data=2 --default-character-set=utf8mb4 \
  server | gzip -9 > /srv/backup/db-$ts.sql.gz
gzip -t /srv/backup/db-$ts.sql.gz && echo dump-ok
```

2. Write a manifest next to the dump: checksum plus row counts for the tables that matter. A restore
   is judged against these numbers, not against the absence of errors.

```bash
sha256sum /srv/backup/db-$ts.sql.gz > /srv/backup/db-$ts.sha256
mariadb -N -B server -e "SELECT 'accounts', COUNT(*) FROM accounts
  UNION ALL SELECT 'vehicles', COUNT(*) FROM vehicles
  UNION ALL SELECT 'houses', COUNT(*) FROM houses" > /srv/backup/db-$ts.counts
```

3. Copy off the host and check the repository itself. A dump on the same disk as the database is not
   a backup, it is a second copy of the same failure.

```bash
export RESTIC_REPOSITORY=s3:https://s3.example.net/omp-backup
restic backup /srv/backup /opt/omp-server/scriptfiles --tag omp
restic check --read-data-subset=5%
```

4. Keep the binlogs. Without them the RPO is "since last night" whatever the table says:

```bash
mariadb-binlog --read-from-remote-server --host=127.0.0.1 --raw --stop-never \
  --result-file=/srv/binlog/mysql-bin. mysql-bin.000001
find /srv/binlog -name 'mysql-bin.*' -mtime +7 -delete
```

5. Write the runbook as commands a second person can run on a fresh host, in this order: provision,
   runtime, schema restore, scriptfiles, config, start. The DB step is one line:

```bash
gunzip -c /srv/backup/db-latest.sql.gz | mariadb --default-character-set=utf8mb4 server
```

6. Drill quarterly on a scratch host and measure the clock. Restoring into a scratch schema catches
   a broken dump without touching production:

```bash
drill_start=$(date +%s)
mariadb -e "DROP DATABASE IF EXISTS drill; CREATE DATABASE drill CHARACTER SET utf8mb4"
gunzip -c /srv/backup/db-latest.sql.gz | mariadb --default-character-set=utf8mb4 drill
mariadb -N -B drill -e "SELECT COUNT(*) FROM accounts"
echo "RTO $(($(date +%s) - drill_start))s"
```

7. Record the drill: date, git tag restored, measured seconds, and every gap found (missing DNS
   record, plugin absent from the runtime manifest, client version mismatch). A drill that only runs
   on the host that already has the server installed has measured nothing.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `ERROR 1049 (42000): Unknown database 'server'` | dump taken without `--databases`, so it carries no `CREATE DATABASE` | restore into an existing schema, or add `--databases` |
| Import succeeds, several tables are short | no `--single-transaction`, players wrote during the dump | add `--single-transaction` and re-take the dump |
| Client rejects the dump with a sandbox-mode error | MariaDB 11 dump piped into an older `mysql` client | use `mariadb` from the same or a newer major version |
| Drill passes, the real restore fails | drill restored from a copy on the same disk | restore from the off-host repository only |
| RTO is hours, not 45 minutes | runtime, DNS and TLS were never in the runbook | script the bootstrap and time it in the drill |
| Row counts match but homes are stale | `scriptfiles` and DB restored from different timestamps | one manifest per run, both assets from the same `ts` |
| Restore stops halfway with no error seen | import piped through a pager or truncated log | never truncate the import; check the exit status |

## Verification

```bash
cd /srv/backup && sha256sum -c db-latest.sha256
gunzip -c db-latest.sql.gz | mariadb --default-character-set=utf8mb4 drill
mariadb -N -B drill -e "SELECT COUNT(*) FROM accounts; SELECT COUNT(*) FROM vehicles"
```

Expected: `db-latest.sql.gz: OK`, then two counts matching the corresponding lines of
`db-latest.counts` exactly, and an elapsed value from the drill at or under 1500 s for the database
slice of the 45-minute RTO. `gzip -t` must exit 0 for each of the last seven dailies.

## Sources (2026)

- https://mariadb.com/kb/en/mariadb-dump/
- https://restic.readthedocs.io/en/stable/010_introduction.html
- https://open.mp/docs/server/LinuxServerInstallation
