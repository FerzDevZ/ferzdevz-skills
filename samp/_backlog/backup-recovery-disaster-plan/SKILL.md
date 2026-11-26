---
name: backup-recovery-disaster-plan
description: Write and test a recovery plan.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# disaster recovery

## When to Use
- Host or disk loss must not erase accounts.
- Nobody knows the restore steps.

## 2026 Compatibility & Architecture Matrix
- Backups off-host, encrypted, with a documented restore.
- State RTO/RPO and test them.

## Production Implementation
1. Document: new host, runtime install, DB restore, scriptfiles restore, start.
2. Run a quarterly drill on a scratch host.
3. Record the drill result and gaps.

```bash
gunzip -c db-latest.sql.gz | mysql server
```

## Deprecated Traps & Edge Cases (2026)
- A plan that assumes the old host exists.
- Restoring without verifying row counts.

## Verification
- A drill restores service on a fresh host; RPO/RTO numbers are recorded.
