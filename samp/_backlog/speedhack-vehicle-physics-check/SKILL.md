---
name: speedhack-vehicle-physics-check
description: Detect vehicle speed hacks against handling data.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, anticheat]
    category: samp
---

# vehicle speed check

## When to Use
- Cars exceed their handling top speed.
- Speed anomalies only appear under load.

## 2026 Compatibility & Architecture Matrix
- Max speed comes from `GetVehicleModelInfo`/handling, plus a tolerance.
- Compare over time, not one sample.

## Production Implementation
1. Read the model's top speed and add 20–30% tolerance.
2. Sample on a timer and count violations.
3. Revert speed or flag the vehicle, then log.

```pawn
new Float:speed = GetVehicleSpeed(vehicleid);
if (speed > g_MaxSpeed[model] * 1.3) LogSpeed(vehicleid, speed);
```

## Deprecated Traps & Edge Cases (2026)
- Ignoring nitro or downhill physics.
- Flagging during a warp or respawn.

## Verification
- Handling-compliant driving never flags.
- A speed hack test is caught within three samples.
