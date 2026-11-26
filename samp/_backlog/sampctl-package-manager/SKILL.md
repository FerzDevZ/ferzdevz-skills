---
name: sampctl-package-manager
description: Pin Pawn dependencies with sampctl and rebuild.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, sampctl]
    category: samp
---

# sampctl dependencies

## When to Use
- A project has includes copied by hand or a build that only works locally.
- You need a pinned YSI/streamer/MySQL version per project.

## 2026 Compatibility & Architecture Matrix
- sampctl 1.17.0 (2026-11-23) resolves `pawn.json` dependencies from GitHub with a lock.
- open.mp runtime can be launched by sampctl, but production should run the pinned `omp-server` binary.

## Production Implementation
1. Declare every dependency in `pawn.json` with a tag, not a branch.
2. Commit the resolved lock and use `sampctl package build` in CI.
3. Verify the AMX is produced and the include list matches the lock.

```json
{"user":"ferz","repo":"gamemode","entry":"gamemodes/main.pwn",
 "dependencies":["pawn-lang/YSI-Includes:5.x","samp-incognito/samp-streamer-plugin:2.9.6"],
 "runtime":{"mode":"server","version":"1.6.7.3218"}}
```

## Deprecated Traps & Edge Cases (2026)
- A dependency on `master` makes yesterday's build unreproducible.
- Mixing sampctl-installed includes with hand-copied ones duplicates definitions.

## Verification
- `sampctl package build` exits 0 and `pawn.json` lists exactly the includes used.
- Build on a clean checkout to prove nothing is taken from the local disk.
