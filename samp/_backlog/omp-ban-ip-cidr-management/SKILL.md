---
name: omp-ban-ip-cidr-management
description: Manage bans including CIDR ranges safely.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, admin]
    category: samp
---

# ban management

## When to Use
- Ban evasion or accidental subnet bans.
- Bans must survive restarts.

## 2026 Compatibility & Architecture Matrix
- Store bans in DB: account id, hashed serial, hashed IP, reason, expiry, evidence id.
- CIDR rules need an explicit staff allowlist.

## Production Implementation
1. Implement ban/unban with audit rows.
2. Check at connect with a cached ban list and invalidate on change.
3. Test ban, expiry and unban.

```pawn
if (IsBanned(ip)) return Kick(playerid);
```

## Deprecated Traps & Edge Cases (2026)
- Banning a /16 without an allowlist.
- A ban row without evidence.

## Verification
- Banned account cannot join; expiry and unban restore access.
