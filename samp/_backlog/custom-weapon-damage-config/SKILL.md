---
name: custom-weapon-damage-config
description: Configure weapon damage server-side.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, combat]
    category: samp
---

# weapon damage config

## When to Use
- Damage values must differ from stock.
- Headshots and armour interact unexpectedly.

## 2026 Compatibility & Architecture Matrix
- Compute damage on the server, never trust the client.
- Use `OnPlayerTakeDamage`/`OnPlayerGiveDamage` with a multiplier table.

## Production Implementation
1. Define a per-weapon damage table in one include.
2. Apply multipliers and armour reduction server-side.
3. Log anomalous damage for review.

```pawn
new Float:dmg = g_WeaponDamage[weapon] * multiplier;
SetPlayerHealth(playerid, health - dmg);
```

## Deprecated Traps & Edge Cases (2026)
- Applying client-reported damage.
- Forgetting armour in the calculation.

## Verification
- Damage matches the table within rounding.
- No one-shot kills from unlisted weapons.
