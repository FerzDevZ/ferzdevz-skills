---
name: stress-test-bot-simulation
description: Load-test with simulated players before release.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, testing]
    category: samp
---

# stress test

## When to Use
- You need to know behaviour at 100+ players.
- A feature only breaks under concurrency.

## 2026 Compatibility & Architecture Matrix
- Bots must speak the same protocol version as real clients.
- Measure tick rate, CPU and DB latency, not just connections.

## Production Implementation
1. Start with 20 bots on a scratch server and ramp in steps.
2. Record tick rate, memory and query latency per step.
3. Fix the first saturation point, then repeat the ramp.

```bash
./samp-bot --host 127.0.0.1 --port 7777 --count 50 --duration 300
```

## Deprecated Traps & Edge Cases (2026)
- Testing on production data.
- Ramping without a cooldown hides the breaking point.

## Verification
- A table of players vs tick rate vs CPU exists for the release.
- The server survives the target player count for 30 minutes.
