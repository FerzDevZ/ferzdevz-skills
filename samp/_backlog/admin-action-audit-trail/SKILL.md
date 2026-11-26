---
name: admin-action-audit-trail
description: Log every administrative action.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security]
    category: samp
---

# admin audit

## When to Use
- Nobody can explain a ban or a balance change.
- A staff member abuses commands.

## 2026 Compatibility & Architecture Matrix
- One table: actor, target, action, before, after, reason, timestamp.
- Write inside the same transaction as the change when possible.

## Production Implementation
1. Wrap admin commands in `AuditAdmin(actor, target, action, before, after)`.
2. Require a reason for destructive actions.
3. Expose the last 50 rows to the panel.

```sql
INSERT INTO admin_actions(actor, target, action, before, after, reason) VALUES (?,?,?,?,?,?);
```

## Deprecated Traps & Edge Cases (2026)
- Logging to chat instead of the database.
- A destructive action without a before/after snapshot.

## Verification
- Every admin command produces a row.
- The panel shows the audit trail for a test account.
