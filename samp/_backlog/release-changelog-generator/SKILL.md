---
name: release-changelog-generator
description: Generate release notes from commits and tags.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ops]
    category: samp
---

# changelog generator

## When to Use
- Releases have no readable notes.
- Players ask what changed.

## 2026 Compatibility & Architecture Matrix
- Conventional commits or PR labels drive categories.
- The git tag is the source of truth.

## Production Implementation
1. Group commits into features, fixes, security, breaking.
2. Write player-facing bullets, not raw messages.
3. Attach the AMX and its sha256.

```bash
git log --pretty='- %s' v1.3.0..v1.4.0
```

## Deprecated Traps & Edge Cases (2026)
- Publishing raw commit messages.
- A release without a breaking-change section when one exists.

## Verification
- Notes match the tag range, list the checksum, and link each fix to its issue.
