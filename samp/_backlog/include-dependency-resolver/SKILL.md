---
name: include-dependency-resolver
description: Resolve Pawn include paths deterministically.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, include]
    category: samp
---

# include resolution

## When to Use
- `fatal error 100: cannot read from file` with an include that exists.
- Two libraries define the same symbol.

## 2026 Compatibility & Architecture Matrix
- pawncc resolves includes relative to `-i` paths in order; sampctl supplies its own.
- omp-stdlib ships `open.mp.inc`, `omp_*.inc` and the legacy `a_*.inc` shims.
- Backslash includes from YSI 5 need patching on Linux.

## Production Implementation
1. Print the effective include list from the build script.
2. Order project includes before third-party ones; never mix two copies of the same library.
3. Compile a one-line probe that includes each dependency alone.

```bash
find . -name '*.inc' | sort | sed 's|^|include: |'
```

## Deprecated Traps & Edge Cases (2026)
- A vendored copy of YSI plus sampctl's copy is the classic duplicate-symbol bug.
- Case-sensitive file systems fail on `<YSI_Data/y_foreach>` style includes.

## Verification
- `pawncc -i` list is logged and the probe file compiles with 0 warnings.
- No duplicate symbol warnings in the full build.
