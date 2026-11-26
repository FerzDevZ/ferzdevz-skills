---
name: omp-pawn-component-sdk-cpp
description: Use when a plugin must become a loadable component.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, cpp, component, sdk]
    category: samp
---

# Ship an open.mp C++ component that the server actually loads

A component is a shared library with one exported C symbol, a UID, and a lifecycle the server
calls in order: `onLoad`, `onInit`, `onReady`. Pawn natives are registered from `onAmxLoad`,
not a global constructor, because no AMX exists when the library is loaded.

## When to Use

- A legacy plugin must move to the component model to see open.mp-only APIs.
- The library compiles but `omp-server` refuses it, or natives come back as "not found".
- You need a native that takes `IPlayer&` instead of a raw `playerid`.

## Compatibility & Stack Matrix (2026)

| Item | Value | Note |
| --- | --- | --- |
| SDK | `openmultiplayer/open.mp-sdk`, clone with `--recursive` | submodules are the interface headers |
| Build | CMake 3.19+, `target_link_libraries(<target> PUBLIC OMP-SDK)` | C++17 |
| Entry point | `COMPONENT_ENTRY_POINT()` expands to `extern "C" SDK_EXPORT IComponent* __CDECL ComponentEntryPoint` | one per library |
| Identity | `PROVIDE_UID(...)` from `https://open.mp/uid` | a missing UID stops the load |
| Lifecycle | `onLoad(ICore*)` -> `onInit(IComponentList*)` -> `onReady()` | register handlers in `onLoad` |
| Pawn natives | `SCRIPT_API` + `pawn_natives::AmxLoad(script.GetAMX())` | wrapper over pawn-natives |
| Install path | `components/` next to `omp-server` | `.so` on Linux, `.dll` on Windows |
| Legacy plugins | old plugin ABI still loads | never mix both SDK headers in one binary |

## Production Implementation

1. Vendor the SDK as a submodule and build a `MODULE` library with no `lib` prefix, so the file
   name on disk matches the component name in the log.

```cmake
cmake_minimum_required(VERSION 3.19)
project(hello_component CXX)
set(CMAKE_CXX_STANDARD 17)
add_subdirectory(external/open.mp-sdk)
add_library(hello MODULE main.cpp)
target_link_libraries(hello PRIVATE OMP-SDK)
set_target_properties(hello PROPERTIES PREFIX "" OUTPUT_NAME "hello")
```
2. Follow the template lifecycle: cache `ICore*` in `onLoad`, query other components in
   `onInit`, and never touch either from a static initialiser.

```cpp
#include <sdk.hpp>
#include <Server/Components/Pawn/pawn.hpp>

class HelloComponent final : public IComponent, public PlayerConnectEventHandler
{
private:
    ICore* core_ = nullptr;
    IPawnComponent* pawn_ = nullptr;

public:
    PROVIDE_UID(/* id from https://open.mp/uid */);

    ~HelloComponent()
    {
        if (core_) core_->getPlayers().getPlayerConnectDispatcher().removeEventHandler(this);
        if (pawn_) pawn_->getEventDispatcher().removeEventHandler(this);
    }

    StringView componentName() const override { return "hello-component"; }
    SemanticVersion componentVersion() const override { return SemanticVersion(1, 0, 0, 0); }

    void onLoad(ICore* c) override
    {
        core_ = c;
        core_->getPlayers().getPlayerConnectDispatcher().addEventHandler(this);
        core_->printLn("hello-component loaded");
        setAmxLookups(core_);
    }

    void onInit(IComponentList* components) override
    {
        pawn_ = components->queryComponent<IPawnComponent>();
        if (pawn_)
        {
            setAmxFunctions(pawn_->getAmxFunctions());
            setAmxLookups(components);
            pawn_->getEventDispatcher().addEventHandler(this);
        }
    }
```
3. Publish natives through `SCRIPT_API` and hand them to every AMX that loads. Without the
   `AmxLoad` call the natives compile in Pawn and fail at run time with "function not found".

```cpp
    void onAmxLoad(IPawnScript& script) override { pawn_natives::AmxLoad(script.GetAMX()); }
    void onAmxUnload(IPawnScript& script) override { }

    void onPlayerConnect(IPlayer& player) override
    {
        core_->printLn("hello-component saw player %d", player.getID());
    }

    void onFree(IComponent* component) override
    {
        if (component == pawn_) { pawn_ = nullptr; setAmxFunctions(); setAmxLookups(); }
    }

    void free() override { delete this; }
    void reset() override { }
};

COMPONENT_ENTRY_POINT()
{
    return new HelloComponent();
}
```

4. Export one naked function: no arguments, no C++ name mangling, no logic beyond constructing
   the component. A native taking a resolved reference is
   `SCRIPT_API(Hello_GetName, bool(IPlayer& player, std::string& out))`.
5. Copy the built library into `components/` and start the server. Loading happens before any
   script runs, and a failure is printed with the library path.

## Failure Modes & Fixes

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Failed to load component` with no name | `ComponentEntryPoint` missing or mangled | export through `COMPONENT_ENTRY_POINT()` and build a `MODULE` library |
| Component loads then disappears | no UID, or a UID already in use | generate a fresh id at `https://open.mp/uid` |
| Pawn script fails with error 19 | `onAmxLoad` never reached | implement `onAmxLoad` and call `pawn_natives::AmxLoad` |
| Crash before any log line | global object touching `ICore` before `onLoad` | move all setup into `onLoad`/`onInit` |
| Crash on unload or `reloadfs` | handler registered after `free()` | unregister in the destructor, null pointers in `onFree` |
| Works locally, fails on the host | different libstdc++ or glibc | build in the same image as the server |
| Duplicate symbol at link time | plugin SDK and component SDK both included | link only `OMP-SDK` |

## Verification

The export must exist exactly once and be unmangled:

```bash
nm -D --defined-only build/hello.so | grep ComponentEntryPoint
```

```text
0000000000004a10 T ComponentEntryPoint
```

Then start the server and read the first two matching log lines:

```bash
cp build/hello.so components/ && ./omp-server > log.txt 2>&1
grep -m2 -i "hello-component" log.txt
```

```text
[Info] hello-component loaded
[Info] hello-component saw player 0
```

Both lines is the proof: the first shows `onLoad` ran, the second shows the connect handler was
registered before any player joined. Only the first line means the registration is missing.

## Sources (2026)

- https://github.com/openmultiplayer/open.mp-sdk
- https://github.com/openmultiplayer/pawn-template/blob/master/main.cpp
