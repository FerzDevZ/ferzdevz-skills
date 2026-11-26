---
name: automated-ci-pawncc-github
description: Compile and test Pawn in GitHub Actions.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ci]
    category: samp
---

# CI for Pawn

## When to Use
- Builds differ between machines.
- No check before deploy.

## 2026 Compatibility & Architecture Matrix
- Ubuntu runner with pawncc 3.10.10 and a cached include set.
- Fail on warnings and a missing AMX.

## Production Implementation
1. Cache includes keyed by the lock file.
2. Compile, start a server, run the test filterscript.
3. Publish the AMX as an artefact on tags.

```yaml
- uses: actions/checkout@v4
- run: sampctl package build
```

## Deprecated Traps & Edge Cases (2026)
- A workflow that only checks out code.
- Ignoring warnings because the exit code is 0.

## Verification
- CI is red on a warning; a tag run publishes the AMX artefact.
