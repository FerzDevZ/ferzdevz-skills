---
name: omp-legacy-plugin-bridge
description: Run a legacy plugin next to open.mp components.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, component]
    category: samp
---

# legacy plugin bridge

## When to Use
- A required plugin has no component build.
- Two providers register the same natives.

## 2026 Compatibility & Architecture Matrix
- Legacy plugins load through plugins/, components through components/.
- A native registered twice is undefined behaviour.

## Production Implementation
1. Inventory native providers and keep one per native.
2. Prefer component builds where they exist.
3. Load components before the gamemode.

```bash
grep -Rh "native " includes/ | sort | uniq -d
```

## Deprecated Traps & Edge Cases (2026)
- Loading both plugin and component for one subsystem.
- Assuming a Windows DLL runs on Linux.

## Verification
- Native list has no duplicates and the server starts; the legacy feature passes its test.
