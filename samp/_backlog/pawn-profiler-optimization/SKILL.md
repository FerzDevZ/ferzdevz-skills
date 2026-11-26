---
name: pawn-profiler-optimization
description: Profile hot Pawn code before optimising.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, profiling]
    category: samp
---

# profiler

## When to Use
- A gamemode uses too much CPU at 100+ players.
- You need evidence for which callback is hot.

## 2026 Compatibility & Architecture Matrix
- The profiler plugin measures per-function time; open.mp also exposes tick rate.
- `OnPlayerUpdate` per tick is the usual culprit.

## Production Implementation
1. Enable the profiler for a fixed window, then sort by total time.
2. Replace per-tick work with timers and dirty flags.
3. Re-measure and compare tick rate and CPU.

```pawn
// profile window: 60 s of normal traffic, then
profiler_write("profile.txt");
```

## Deprecated Traps & Edge Cases (2026)
- Optimising without a profile usually moves the bottleneck.
- Micro-optimising a function called once per minute.

## Verification
- Before/after CPU and tick-rate numbers with the same player count.
- Hot function no longer in the top 5.
