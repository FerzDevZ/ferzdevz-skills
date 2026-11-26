---
name: ysi-y-ini-legacy-storage
description: Read legacy Y_INI files without rewriting the format.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# y_ini legacy

## When to Use
- An existing server stores accounts in `.ini`.
- You need migration, not a rewrite.

## 2026 Compatibility & Architecture Matrix
- `y_ini` still works but is legacy; new projects use MySQL.
- Reading is safe; writing must keep the same key names for other tools.

## Production Implementation
1. Parse with `INI_Load` and map fields to the current model.
2. Migrate to SQL in one batch with a verification count.
3. Keep the `.ini` files read-only after migration.

```pawn
#include <YSI_Storage/y_ini>
INI_Load("users/%s.ini", name);
```

## Deprecated Traps & Edge Cases (2026)
- Two writers on the same `.ini` corrupt it.
- Assuming UTF-8 in files written by a CP1251 tool.

## Verification
- Migrated row count equals the `.ini` file count.
- A sample account loads with the same money and level.
