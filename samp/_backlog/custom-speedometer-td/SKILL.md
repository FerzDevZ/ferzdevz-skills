---
name: custom-speedometer-td
description: Draw a speedometer from vehicle data.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, textdraw]
    category: samp
---

# speedometer

## When to Use
- Speedometer lags or shows the wrong unit.
- KM/H vs MPH conversion is wrong.

## 2026 Compatibility & Architecture Matrix
- Update on a 100–200 ms timer, not per tick.
- Speed unit conversion: km/h = m/s * 3.6.

## Production Implementation
1. Read vehicle velocity, compute km/h, format into a PlayerTD.
2. Hide when not in a vehicle.
3. Clamp and round for stable digits.

```pawn
new Float:vx, Float:vy, Float:vz; GetVehicleVelocity(v, vx, vy, vz);
new Float:kmh = floatsqroot(vx*vx + vy*vy + vz*vz) * 136.666;
```

## Deprecated Traps & Edge Cases (2026)
- Formatting every frame causes flicker and CPU cost.
- Showing km/h while the label says mph.

## Verification
- Stationary shows 0 and a known speed matches the handling table.
- CPU is flat with 50 vehicles.
