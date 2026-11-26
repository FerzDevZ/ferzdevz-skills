---
name: omp-c-api-gdk
description: Call Pawn natives from C and ship a GDK module.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, cpp, sdk]
    category: samp
---

# open.mp C API / GDK

## When to Use

- A native C/C++ module must read or change game state that only Pawn exposes.
- You are writing server logic outside Pawn and need Scripting API access.

## 2026 Compatibility & Architecture Matrix

| Capability | Since | Note |
| --- | --- | --- |
| C API + C API SDK | v1.5.8.3079 | official, ships with the server |
| Call Pawn natives from C++ SDK | v1.5.8.3079 | removes the AMX-shim hacks |
| C++ component SDK | earlier | still the route for components inside the server |
| Non-Pawn gamemodes via GDK | blog: release-candidate-1 | supported direction |

## Production Implementation

1. Declare the interface you depend on, and check it at load time instead of assuming:

```cpp
#include <api.hpp>   // C API SDK header shipped with the server

static ICore* core = nullptr;
static IPawnComponent* pawn = nullptr;

void OnLoad(ICore* c)
{
    core = c;
    pawn = c->getPawnComponent();   // exact getter per installed SDK header
    if (!pawn) {
        core->printLn("pawn component missing; GDK disabled");
        return;
    }
}
```

2. Call a Pawn native from C++ only on the server thread. Queue work from other threads:

```cpp
// pseudo-signature: consult IPawnComponent in the header you build against
// pawn->CallNative("SetPlayerHealth", "if", playerid, 100.0f);
```

3. Build and ship exactly like a component: one shared object in `components/`, plus its
   dependency libs. The server loads components recursively (see
   `omp-component-load-order`).

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
cp build/libmygdk.so /srv/omp/components/
```

## Deprecated Traps & Edge Cases (2026)

- Guessing native names or argument format strings: read them from the Pawn include and
  test one call before writing logic.
- Calling from a worker thread corrupts the AMX stack; marshal to the main thread.
- Linking against a different SDK version than the running server: interface version
  mismatch, silent no-load.
- Treating the C API as stable forever: pin the header version in your repo.

## Verification

- Server log shows the component loaded and the interface version, not "failed to load".
- One round trip works: C++ sets a value, Pawn reads it, logs agree.
- `nm -D build/libmygdk.so | grep OnLoad` shows the exported entry point.

## Sources (2026)

- https://open.mp/docs/changelog (v1.5.8.3079)
- https://github.com/openmultiplayer/open.mp
- https://www.open.mp/blog/release-candidate-1
