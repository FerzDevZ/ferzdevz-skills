---
name: pawn-raknet-packet-guard
description: Validate packet fields before applying them.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, security]
    category: samp
---

# packet field guard

## When to Use
- A crafted packet sets an impossible weapon or position.
- Values from the wire reach game state.

## 2026 Compatibility & Architecture Matrix
- Every id, ammo count and float needs a range.
- Pawn.RakNet can rewrite or drop a packet, not just log it.

## Production Implementation
1. Read fields with checked accessors and validate ranges.
2. Clamp or drop; never partially apply.
3. Log anomalies with the raw bytes for replay.

```pawn
if (weapon < 0 || weapon > WEAPON_PISTOL) return 0;
if (ammo < 0 || ammo > MAX_AMMO) return 0;
```

## Deprecated Traps & Edge Cases (2026)
- Trusting a float for position without NaN checks.
- Applying half a packet after a failed read.

## Verification
- Fuzzed packets are rejected and logged.
- No state change occurs for an invalid packet.
