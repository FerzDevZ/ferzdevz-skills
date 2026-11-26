---
name: git-gamemode-workflow
description: Version a gamemode with branches, tags and reviewed merges.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, git]
    category: samp
---

# git workflow for gamemodes

## When to Use
- Multiple developers touch the same callbacks.
- You need to roll back a bad live release.

## 2026 Compatibility & Architecture Matrix
- Compiled `.amx` files are artefacts, not sources; tag the source and keep the AMX in releases.
- One owner per subsystem prevents merge conflicts in `OnGameModeInit`.

## Production Implementation
1. Protect `main`, work on short branches, require a compile check in CI.
2. Tag releases `vX.Y.Z` and attach the AMX plus changelog.
3. Never commit credentials or `scriptfiles` player data.

```bash
git tag -a v1.4.0 -m "economy rework" && git push --tags
```

## Deprecated Traps & Edge Cases (2026)
- Committing the AMX causes binary conflicts nobody can review.
- A `.gitignore` that excludes includes breaks reproducible builds.

## Verification
- CI compiles the tagged commit with 0 warnings.
- Release page has the AMX and the changelog.
