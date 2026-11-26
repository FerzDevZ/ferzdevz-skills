---
name: omp-component-load-order
description: Control which component loads first, and why.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, components, ops]
    category: samp
---

# Component load order

## When to Use

- Two components fight over the same hook, or one needs another already loaded.
- A component loads on Windows but not on Linux.

## 2026 Compatibility & Architecture Matrix

| Behaviour | Since | Consequence |
| --- | --- | --- |
| Recursive loading in subfolders | v1.4.0.2779 | folder layout is part of the contract |
| `$`-prefixed components load sooner | v1.4.0.2779 | the documented priority knob |
| `$` components load with `RTLD_GLOBAL` on Linux | v1.4.0.2779 | symbol visibility differs from normal components |
| Interface version check | component SDK | mismatch = silent no-load |

## Production Implementation

1. Make the order explicit in the filesystem, not in a readme:

```text
components/
  $core/            <- loads first, RTLD_GLOBAL
    libdb.so
  $security/
    libguard.so
  gameplay/
    libjobs.so
    libinventory.so
```

2. Within a tier, order is alphabetical, so name files for the dependency chain
   (`lib10_db.so`, `lib20_cache.so`).

3. State the dependency in code and fail loudly:

```cpp
void OnLoad(ICore* c)
{
    if (!c->getComponent("DB")) {
        c->printLn("libcache: DB component not loaded; refusing to start");
        return;   // do not deregister silently
    }
}
```

4. Simulate the order before deploying:

```bash
python3 ~/.hermes/skills/samp/omp-component-load-order/scripts/plan_load_order.py /srv/omp/components
```

## Deprecated Traps & Edge Cases (2026)

- Relying on directory iteration order: it changed when recursive loading was added.
- Putting a library both in `components/` and in the system loader path: two copies, one
  wins unpredictably.
- `$` prefix on a component that then exports symbols other components rely on: with
  `RTLD_GLOBAL` this "works", which hides a real linking bug until a machine differs.

## Verification

- `plan_load_order.py` output matches the order printed by the server at boot.
- Removing a dependency produces your explicit error line, not a crash.
- On Linux, `LD_DEBUG=libs ./omp-server 2>&1 | grep RTLD` shows the `$` component scoped
  globally.

## Sources (2026)

- https://open.mp/docs/changelog (v1.4.0.2779)
- https://github.com/openmultiplayer/open.mp
