---
name: dynamic-pagination-dialog
description: Paginate long lists in dialogs.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ui]
    category: samp
---

# dialog pagination

## When to Use
- A list has hundreds of items and the dialog truncates.
- Page state is lost on response.

## 2026 Compatibility & Architecture Matrix
- Dialogs have a practical row limit; paginate 10–20 per page.
- Page index must be stored per player.

## Production Implementation
1. Store the list and page per player, render one page per dialog.
2. Map listitem to `page*size + listitem` and validate.
3. Add prev/next entries with explicit ids.

```pawn
new idx = g_Page[playerid] * PAGE + listitem;
if (idx >= g_Count) return 0;
```

## Deprecated Traps & Edge Cases (2026)
- Trusting listitem as a global index.
- Losing page state when the dialog reopens.

## Verification
- Last page shows the remainder and no out-of-range action.
- Navigation keeps the same selection semantics.
