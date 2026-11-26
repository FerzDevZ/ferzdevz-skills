---
name: mapping-collision-colandreas-bake
description: Bake collision for custom maps.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mapping]
    category: samp
---

# collision bake

## When to Use
- Custom buildings are walk-through.
- ColAndreas does not know the new objects.

## 2026 Compatibility & Architecture Matrix
- ColAndreas handles model collision; custom objects need a COL or a supported loader.
- MapAndreas is terrain height only.

## Production Implementation
1. Add COL data for custom models where applicable.
2. Or restrict players with server-side bounds on walkable areas.
3. Test perimeter, roof and stairs with a player.

```pawn
CA_RayCastLine(x, y, z + 1.0, x, y, z - 5.0, hx, hy, hz);
```

## Deprecated Traps & Edge Cases (2026)
- Assuming the visual mesh is collision.
- Baking collision for objects that later move.

## Verification
- Raycast hits the custom building; walking tests pass at edges and stairs.
