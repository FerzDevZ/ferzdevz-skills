---
name: omp-component-load-order
description: Use when two components load in the wrong order.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, components, ops, sdk]
    category: samp
---

# Component load order: name the dependency, not the alphabet

## When to Use

- A Pawn native reports "function not found" because its component registered before the component
  that provides the symbol was ready.
- A legacy plugin listed in `pawn.legacy_plugins` calls another plugin's native during its own load.
- The same `components/` folder works on Windows and silently drops a component on Linux.
- You are about to rename a file to `$something` and want to know what that changes for everything else.
- You want the load order reviewable in the repo instead of implied by directory iteration.

## Compatibility & Stack Matrix (2026)

| Layer | Knob | Behaviour in 2026 builds |
| --- | --- | --- |
| Component discovery | `components/` directory | recursive scan, so subfolders are part of the contract |
| Early tier | file name starting with `$` | collected before all others, opened with `RTLD_GLOBAL` on Linux |
| Lifecycle | `onLoad` -> `onInit` -> `onReady` | every component gets `onLoad`, then all get `onInit`, then all get `onReady` |
| Dependency lookup | `IComponentList::queryComponent<T>()` | returns `nullptr` when the provider is absent or its interface UID differs |
| Legacy plugins | `config.json` -> `pawn.legacy_plugins` | loaded in array order, before any script |
| Gamemode / filterscripts | `pawn.main_scripts`, `pawn.side_scripts` | loaded in array order, entries are `"name 1"` |
| Interface version | SDK `supportedVersion()` | mismatch prints `Built for open.mp version N, now on M` and skips the component |

There is no `load_order` key in `config.json` and no dependency field in a component manifest. Order
is expressible only through the filesystem, the `pawn.*` arrays and the lifecycle hooks above.

## Production Implementation

1. Order the Pawn layer explicitly. These are the only ordering keys the docs promise, and array
   position is the order the server uses:

```json
{
  "pawn": {
    "legacy_plugins": ["sscanf", "streamer", "Pawn.RakNet"],
    "main_scripts": ["core 1"],
    "side_scripts": ["filterscripts/anticheat"]
  }
}
```

2. Fix the native component order in the filesystem. Anything a later component links against goes in
   the `$` tier; keep that tier small, because `RTLD_GLOBAL` also hides genuine link errors:

```text
components/
  $libcrypto/          # loaded first, symbols global on Linux
    crypto.so
  $database/
    PostgreSQL.so
  gameplay/
    libjobs.so         # links against $libcrypto at runtime
    libinventory.so
```

3. Do not resolve dependencies in `onLoad`. At that point the provider may not be loaded and the query
   returns `nullptr` for a component that is about to appear. `onInit` receives the assembled list and
   is the documented place for it:

```cpp
#include <Server/Components/Pawn/pawn.hpp>

struct CacheComponent final : public IComponent
{
    ICore* core_ = nullptr;
    IPawnComponent* pawn_ = nullptr;
    bool ready_ = false;

    void onLoad(ICore* c) override { core_ = c; }

    void onInit(IComponentList* components) override
    {
        pawn_ = components->queryComponent<IPawnComponent>();
        if (!pawn_)
        {
            core_->printLn("libcache: Pawn component missing, natives not registered");
            return;                       // dependency absent: stay unloaded
        }
        ready_ = true;
    }

    void onReady() override
    {
        if (!ready_) return;              // never half-register natives
        // register Pawn natives here
    }

    UID getUID() const override { return UID(0xa11c0001); }
    StringView componentName() const override { return "libcache"; }
    SemanticVersion componentVersion() const override { return SemanticVersion(1, 0, 0); }
    void free() override {}
    void reset() override {}
};
```

4. Register Pawn natives in `onReady`, never in `onLoad`, and only after the `onInit` gate passed. A
   component that registers half its natives and then discovers a missing dependency leaves the script
   calling into a null implementation.

5. Keep one copy of each library. The loader scans `components/` recursively and also loads
   `pawn.legacy_plugins` from `plugins/`; the same library in both places loads twice and the second
   copy loses the UID conflict:

```text
[Info] Tried to add plug-ins libcache.so and libcache.so with conflicting UID 00000000a11c0001
```

6. Record the order you expect in the repo, next to the components, so a review can diff it:

```bash
find components -type f \( -name '*.so' -o -name '*.dll' \) | sort > expected-order.txt
```

That sort is alphabetical, so read the file as two blocks: basenames starting with `$` load first,
everything else after. Keep the numeric prefix inside each block (`crypto.so`, then `PostgreSQL.so`)
because scan order within a tier is not a documented contract.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Native "not found" in the script, component logged as loaded | natives registered in `onLoad` before the provider's `onInit` | resolve in `onInit`, register in `onReady` |
| Component missing from the Linux log with no error | shipped a `.dll`, or the SDK interface version differs | ship `.so`; read the `Built for open.mp version` line |
| Component loads but `queryComponent<T>()` returns `nullptr` | provider loaded later, or headers disagree on the interface UID | one SDK version across all components; query in `onInit` |
| Unknown symbol at boot inside a `$` component | `RTLD_GLOBAL` exposed an unresolved symbol that should have failed the link | keep real shared libraries in `$`, gameplay code out |
| `pawn.legacy_plugins` entry ignored | written as `plugins/streamer.so` | bare name, no extension or path |
| UID conflict line at boot | same library in `components/` and `plugins/` | keep one location |
| Order changes after a rename | filesystem scan order is not a contract | encode the tier in the name (`$`, numeric prefix) and assert in the log |

## Verification

```bash
./omp-server 2>&1 | grep -E "Loading component|Built for open.mp|conflicting UID" | head -20
```

Expected on a correct tree: the `$` tier first, gameplay second, no conflict line at all.

```text
[Info] Loading component crypto.so
[Info] Loading component PostgreSQL.so
[Info] Loading component libjobs.so
[Info] Loading component libinventory.so
```

- Manual: delete `$database/PostgreSQL.so`, restart, and confirm `libcache: Pawn component missing`
  is printed instead of a crash — the `onInit` gate turns a missing dependency into a log line.
- Cross-check the recorded file order against the log order once per release; a diff here means
  somebody renamed a library between the review and the deploy.

## Sources (2026)

- https://open.mp/docs/server/config.json — section Pawn: `pawn.main_scripts`, `pawn.side_scripts`,
  `pawn.legacy_plugins`.
- https://github.com/openmultiplayer/open.mp/pull/1020 — `$` components load first and with
  `RTLD_GLOBAL` on Linux; the diff also shows the recursive directory scan.
- https://open.mp/docs/server/Installation — which libraries belong in `components/` rather than
  `plugins/`.
