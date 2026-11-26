---
name: omp-server-query-api
description: Expose server information and rules through queries.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, api]
    category: samp
---

# server query API

## When to Use
- A website or launcher needs live server data.
- Rules must reflect gamemode state.

## 2026 Compatibility & Architecture Matrix
- open.mp supports server rules (`SetServerRule`, `AddServerRule`) published on the query port.
- Query data is public; never put secrets in rules.

## Production Implementation
1. Set hostname, mode and language at start.
2. Update player counts on change, not per tick.
3. Verify with an external query client.

```pawn
SetServerRule("mode", "Freeroam");
```

## Deprecated Traps & Edge Cases (2026)
- Publishing secrets or admin counts as rules.
- Updating rules every tick.

## Verification
- An external query sees hostname, players and rules; values change after a join.
