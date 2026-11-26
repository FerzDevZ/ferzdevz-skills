---
name: crafting-blueprint-system
description: Implement crafting with validated recipes.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, gameplay]
    category: samp
---

# crafting

## When to Use
- Players craft without ingredients.
- Recipe ids come from the client.

## 2026 Compatibility & Architecture Matrix
- Recipes are server data: inputs, outputs, time, station.
- Validate ingredient counts before consuming.

## Production Implementation
1. Define blueprints in one include/table.
2. Consume inputs and add outputs in a transaction.
3. Add a craft time and cancel path.

```pawn
if (!HasIngredients(playerid, recipe)) return 0;
```

## Deprecated Traps & Edge Cases (2026)
- Checking only one ingredient.
- Allowing crafting while dead or in a vehicle.

## Verification
- Missing ingredients reject cleanly.
- Counts stay consistent after cancel.
