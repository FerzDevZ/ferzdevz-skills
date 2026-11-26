---
name: omp-mysql-component-setup
description: Use the open.mp MySQL component instead of a legacy plugin.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, mysql]
    category: samp
---

# omp MySQL component

## When to Use
- Migrating from BlueG on open.mp.
- You want a maintained component with the same SQL surface.

## 2026 Compatibility & Architecture Matrix
- open.mp components live in `components/` and load without `plugins` entries.
- The component/plugin choice must be one per server.

## Production Implementation
1. Install the component for the server arch.
2. Point the include at the omp variant and recompile.
3. Run the same account load/save test.

```bash
ls components/ | grep -i mysql
```

## Deprecated Traps & Edge Cases (2026)
- Loading both the legacy plugin and the component duplicates natives.
- Mixing include versions produces incompatible hash functions.

## Verification
- Log shows the component loaded and account save/load passes.
- `nm -D` shows one MySQL implementation.
