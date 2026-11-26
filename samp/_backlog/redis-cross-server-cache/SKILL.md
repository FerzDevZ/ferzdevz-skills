---
name: redis-cross-server-cache
description: Share state across servers with Redis.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, cache]
    category: samp
---

# Redis cache

## When to Use
- Two servers must see the same online list or bans.
- DB reads are the bottleneck.

## 2026 Compatibility & Architecture Matrix
- Redis is a cache, not the source of truth; the DB remains authoritative.
- Use TTLs and versioned keys.

## Production Implementation
1. Write-through from the owning service with a TTL.
2. Read with fallback to DB and repopulate.
3. Invalidate on ban/economy changes explicitly.

```bash
redis-cli SET online:12 '{"name":"Ferz"}' EX 60
```

## Deprecated Traps & Edge Cases (2026)
- Caching money without invalidation causes duplication.
- Keys without namespacing collide across environments.

## Verification
- Killing Redis only degrades latency, not correctness.
- Ban changes take effect on all servers within the TTL.
