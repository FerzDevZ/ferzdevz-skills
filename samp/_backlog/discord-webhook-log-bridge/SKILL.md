---
name: discord-webhook-log-bridge
description: Send important server events to Discord.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# Discord bridge

## When to Use
- Admins miss crashes or bans.
- The channel floods with noise.

## 2026 Compatibility & Architecture Matrix
- The webhook URL is a secret; batch and rate limit.
- Send only actionable events.

## Production Implementation
1. Queue events and flush every few seconds.
2. Redact IPs and secrets before sending.
3. Back off on HTTP 429.

```bash
curl -H 'Content-Type: application/json' -d '{"content":"server restarted"}' "$WEBHOOK"
```

## Deprecated Traps & Edge Cases (2026)
- One message per tick.
- Committing the webhook URL.

## Verification
- A crash produces one message within seconds; no duplicates under load.
