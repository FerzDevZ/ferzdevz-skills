---
name: omp-pawn-component-sdk-cpp
description: Build an open.mp C++ component that loads.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, component]
    category: samp
---

# component SDK

## When to Use
- A plugin must move to the component model.
- The component compiles but the server refuses it.

## 2026 Compatibility & Architecture Matrix
- open.mp C++ SDK components export COMPONENT_ENTRYPOINT/EXITPOINT; interface version must match.
- Legacy plugin ABI stays valid for Pawn natives.

## Production Implementation
1. Copy the official component template and rename the target.
2. Register events/natives only from `OnLoad`.
3. Build against the same libc as the server and load it.

```cpp
extern "C" COMPONENT_EXPORT IComponent* ComponentEntryPoint() { return new MyComponent(); }
```

## Deprecated Traps & Edge Cases (2026)
- Static initialisers touching ICore before OnLoad.
- Mixing two SDK copies in one binary.

## Verification
- Server log shows the component loaded and one event fires.
- `component.json` interface version matches the server.
