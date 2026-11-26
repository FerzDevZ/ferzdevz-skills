---
name: automated-db-backup-cron
description: Automate database backups that can be restored.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# DB backups

## When to Use
- A backup has never been restored.
- Disk or corruption incident needs a plan.

## 2026 Compatibility & Architecture Matrix
- `mysqldump --single-transaction` for InnoDB; keep 7 daily + 4 weekly off-host.
- Encrypt and checksum the dump.

## Production Implementation
1. Cron the dump with a timestamped name and sha256.
2. Copy off-host and prune by retention.
3. Monthly restore into a scratch DB and run a count query.

```bash
mysqldump --single-transaction db | gzip > /backup/db-$(date +%F).sql.gz
```

## Deprecated Traps & Edge Cases (2026)
- Backups on the same disk.
- A dump that fails silently because the password file moved.

## Verification
- Restore drill passes and row counts match.
- Backup age alert fires if the newest file is older than 26h.
