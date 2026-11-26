---
name: ysi-y-va-variadic-args
description: Format strings without buffer overflows using y_va.
version: "2026.1.0"
metadata:
  hermes:
    tags: [samp, openmp, pawn, ysi]
    category: samp
---

# y_va

## When to Use
- `format` with a destination smaller than the input truncates silently.
- You need a safe printf wrapper.

## 2026 Compatibility & Architecture Matrix
- `y_va` provides `va_format`/`va_return` helpers that size the buffer.
- Pawn has no dynamic strings; every buffer has a cap.

## Production Implementation
1. Use `va_format(dest, sizeof dest, fmt, ...)` for messages.
2. Cap user input before formatting.
3. Test with a 512-character name and a UTF-8 message.

```pawn
#include <YSI_Coding/y_va>
new msg[144]; va_format(msg, sizeof msg, "Player %s joined", name);
```

## Deprecated Traps & Edge Cases (2026)
- `strcat` into a fixed buffer without checking the remaining size.
- Assuming `format` truncates at a word boundary; it cuts bytes.

## Verification
- Oversized input produces a truncated message with no crash.
- No `format` warnings in the build.
