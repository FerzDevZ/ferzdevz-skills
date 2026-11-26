---
name: ufw-ddos-raknet-mitigation
description: Mitigate RakNet floods at the host level.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security]
    category: samp
---

# DDoS mitigation

## When to Use
- The server drops under packet floods.
- Connection floods exhaust slots.

## 2026 Compatibility & Architecture Matrix
- UDP floods need provider-level protection plus open.mp network limits.
- `network.messages_limit` (default 500/s) and `network.limits_ban_time` are the app-layer knobs.

## Production Implementation
1. Enable provider DDoS protection and monitor packet rate.
2. Set network limits and the connection grace period.
3. Alert on connection failures and packet-rate spikes.

```bash
ufw allow 7777/udp
# rate limit with nftables rather than dropping all UDP
```

## Deprecated Traps & Edge Cases (2026)
- A stateful firewall rule that drops legitimate UDP.
- Relying only on the application layer.

## Verification
- Normal traffic passes, a flood test is rate-limited, and the log shows bantime events.
