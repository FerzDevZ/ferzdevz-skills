---
name: custom-include-api-design
description: Design a project include other developers can use.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, include]
    category: samp
---

# include API design

## When to Use
- A subsystem is copied between gamemodes.
- You need a stable public API.

## 2026 Compatibility & Architecture Matrix
- One include, one prefix, one version macro.
- Public functions documented; internals in a separate implementation include.

## Production Implementation
1. Define the prefix (`hz_`), version and error codes in the header.
2. Expose only functions the gamemode needs.
3. Add a two-line usage example that compiles.

```pawn
#if !defined HZ_INC_VERSION
    #define HZ_INC_VERSION (202601)
#endif
native hz_Start();
```

## Deprecated Traps & Edge Cases (2026)
- Exposing globals instead of functions locks callers to your internals.
- A prefix collision with another library breaks compilation.

## Verification
- A fresh gamemode including only the header compiles.
- The example runs and returns the documented codes.
