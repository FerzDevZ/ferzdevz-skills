---
name: player-report-ticket-system
description: Collect and triage player reports.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, support]
    category: samp
---

# report tickets

## When to Use
- Reports get lost in chat.
- Staff cannot track resolution.

## 2026 Compatibility & Architecture Matrix
- Persist tickets with reporter, target, reason, evidence and state.
- Rate-limit submissions.

## Production Implementation
1. Add `/report` with a validated category.
2. Store, notify staff, allow state transitions.
3. Expose history in the panel.

```sql
INSERT INTO tickets(reporter, target, category, body, state) VALUES (?,?,?,?, 'open');
```

## Deprecated Traps & Edge Cases (2026)
- Unbounded report spam.
- Closing a ticket without a resolution note.

## Verification
- A report appears once and moves through states; spam is rate-limited.
