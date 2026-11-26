---
name: omp-unicode-utf8-chat
description: Handle UTF-8 text in chat and names.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, i18n]
    category: samp
---

# UTF-8 handling

## When to Use
- Names or chat show mojibake.
- Validation cuts multibyte characters in half.

## 2026 Compatibility & Architecture Matrix
- open.mp reads UTF-8; rendering varies by client build.
- Byte length differs from character count for multibyte scripts.

## Production Implementation
1. Store text as UTF-8 / `utf8mb4`.
2. Validate bytes for buffer safety and characters for policy.
3. Test accented and CJK names end to end.

```sql
ALTER TABLE accounts CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

## Deprecated Traps & Edge Cases (2026)
- Truncating at an arbitrary byte boundary.
- Assuming CP1251 on legacy clients.

## Verification
- Accented names store and display correctly; a 24-character test is not cut mid-character.
