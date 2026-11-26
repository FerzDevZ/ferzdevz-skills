---
name: android-mobile-client-sync-guard
description: Keep mobile clients in sync without trusting them.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mobile]
    category: samp
---

# mobile sync guard

## When to Use
- Mobile players desync after alt-tab or network change.
- The Android client sends bursts after resuming.

## 2026 Compatibility & Architecture Matrix
- SA-MP Android clients vary in build; open.mp `network.allow_037_clients` controls 0.3.7 compatibility.
- Bursts after resume trigger rate limits and anticheat.

## Production Implementation
1. Rate-limit per player with a short grace after resume.
2. Validate state on resume instead of trusting the first burst.
3. Log the resume event for correlation with reports.

```pawn
if (GetTickCount() - g_LastResume[playerid] < 3000) return 1; // grace
```

## Deprecated Traps & Edge Cases (2026)
- Treating a resume burst as a cheat.
- Assuming the mobile client sends the same field order as PC.

## Verification
- Alt-tab resume produces no kicks.
- A genuine cheat during the grace window is still caught after it.
