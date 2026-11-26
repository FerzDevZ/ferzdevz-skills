---
name: omp-c-api-gdk
description: Use when a C++ GDK module must reach Pawn or core state.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, cpp, sdk, component, gdk]
    category: samp
---

# Ship a C++ module against the open.mp component SDK

The 2026 route for C++ outside Pawn is the component SDK (GDK): one shared object the server
loads, subclassing `IComponent`, registering Pawn natives with `SCRIPT_API`. The failure is
never "C++ is hard" — it is building against headers that do not match the running server, or
copying an API name from a blog post instead of reading the header you link.

## When to Use

- A C++ module must read or change server state that only the core exposes (players, pools,
  network, Pawn scripts).
- You want extra Pawn natives without rebuilding the whole gamemode, e.g. a lookup table
  large enough that Pawn memory is the bottleneck.
- A legacy plugin works but the team wants a component instead of a bridge (`omp-legacy-plugin-bridge`).

## Compatibility & Stack Matrix (2026)

| Layer | 2026 baseline | Note |
| --- | --- | --- |
| Server | open.mp 1.6.7.3218 | components load from `components/` |
| Component SDK | `openmultiplayer/open.mp-sdk` master | vendor as a submodule, pin the commit |
| Entry headers | `include/component.hpp`, `include/sdk.hpp` | `IComponent`, `COMPONENT_ENTRY_POINT()` |
| Pawn headers | `include/Server/Components/Pawn/pawn.hpp` | `IPawnComponent`, `PawnEventHandler`, script events |
| Native macros | `Server/Components/Pawn/Impl/pawn_natives.hpp` | `SCRIPT_API`, `pawn_natives::AmxLoad` |
| CMake target | `OMP-SDK` from `add_subdirectory(...)` | link it `PRIVATE` |
| UID | `PROVIDE_UID(...)` from `https://open.mp/uid` | one per component, one per extension |

Header and target names above are from the SDK tree; the exact accessor you call is declared in
those headers. Read them in your checkout — a signature copied from a forum post is how a
component loads and then crashes on its first call.

## Production Implementation

1. Vendor the SDK once and link the target it exports. Do not carry loose copies of the
   headers in your tree; a stale header is a silent ABI mismatch:

```cmake
cmake_minimum_required(VERSION 3.19)
project(trackguard LANGUAGES C CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_subdirectory(third_party/open.mp-sdk)
add_library(trackguard SHARED main.cpp)
target_link_libraries(trackguard PRIVATE OMP-SDK)
```

2. Include exactly what you use. `sdk.hpp` pulls the interfaces, `pawn.hpp` the Pawn
   component, `pawn_natives.hpp` the `SCRIPT_API` machinery:

```cpp
#include <sdk.hpp>
#include <Server/Components/Pawn/pawn.hpp>
#include <Server/Components/Pawn/Impl/pawn_natives.hpp>
```

3. Subclass `IComponent` and take the interfaces you need in `onLoad`. Cache them; the core
   hands out references that stay valid for the life of the component:

```cpp
class TrackGuard final : public IComponent, public PawnEventHandler {
    ICore* core_ = nullptr;
    IPawnComponent* pawn_ = nullptr;

public:
    PROVIDE_UID(0x0000000000000000ULL); // replace with a UID from https://open.mp/uid

    void onLoad(ICore* c) override {
        core_ = c;
        pawn_ = &c->getPawnComponent();   // declared in pawn.hpp
        pawn_->getEventDispatcher().addEventHandler(this);
    }

    void onAmxLoad(IPawnScript& script) override {
        pawn_natives::AmxLoad(script.GetAMX());  // registers every SCRIPT_API below
    }

    void free() override { delete this; }
};
```

4. Register natives with `SCRIPT_API`. Return `bool` when the caller can be told the call
   failed; the macro resolves `IPlayer&` from the Pawn `playerid` argument for you:

```cpp
SCRIPT_API(TrackGuardCount, int())
{
    return 0; // replace with the counter you keep
}

SCRIPT_API(TrackGuardFlagPlayer, bool(IPlayer& player, int reason))
{
    // player is already resolved from playerid and validated by the SDK
    if (reason < 0) return false;
    return true;
}
```

5. Export the entry point once, at file scope. `COMPONENT_ENTRY_POINT()` is what the server
   looks for after loading the library; two in one binary is a load failure:

```cpp
COMPONENT_ENTRY_POINT()
{
    return new TrackGuard();
}
```

6. Build Release, copy the shared object into `components/`, restart. Components load in
   filesystem order unless you pin it — read `omp-component-load-order` before depending on
   another component being up.

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
cp build/libtrackguard.so /srv/omp/components/trackguard.so
```

7. Call into Pawn only from the main thread. Player and entity containers are not
   thread-safe; if a worker produces a result, hand it back through an event and touch
   `IPawnComponent` there. A component that calls script functions from a pool thread
   corrupts the AMX stack under load, never in the first test.

8. Version the pair: record the SDK commit next to the server version and fail CI when they
   drift (`git -C third_party/open.mp-sdk rev-parse --short HEAD` against a pinned file).

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| Component never appears in the log | `COMPONENT_ENTRY_POINT()` missing or duplicated | exactly one at file scope, confirm the export with `nm -D` |
| Server aborts while loading | built against different SDK headers than the server | rebuild against the pinned SDK commit, redeploy both |
| Native is "unknown" in Pawn | `onAmxLoad` did not call `pawn_natives::AmxLoad` | forward `script.GetAMX()` in `onAmxLoad` |
| Crash on the first native call | interface fetched from a null component pointer | check the pointer in `onLoad`, log and disable instead of dereferencing |

## Verification

The binary must resolve every SDK symbol at load time and export exactly one entry point.
Both checks run in the deploy script before the restart:

```bash
ldd -r build/libtrackguard.so | grep -c 'undefined symbol'; nm -D --defined-only build/libtrackguard.so | grep -ci entry
```

Expected on a good build — nothing unresolved, one entry export:

```text
0
1
```

After restart the log shows the `onLoad` banner and one `/trackguard` call returns a number —
the only proof the native is registered against the running script, not just compiled.

## Sources (2026)

- https://github.com/openmultiplayer/open.mp-sdk — header tree: `component.hpp`, `sdk.hpp`, `Server/Components/Pawn/pawn.hpp`, CMake target `OMP-SDK`.
- https://github.com/openmultiplayer/pawn-template — reference component: `COMPONENT_ENTRY_POINT()`, `SCRIPT_API`, `PROVIDE_UID`, `onAmxLoad`.
- https://open.mp/docs/changelog — component and C API revisions per server release.
